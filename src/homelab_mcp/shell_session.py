"""Web-based interactive shell session management."""

import asyncio
import logging
import secrets
import time
from dataclasses import dataclass

import asyncssh

from .ssh_connection import ssh_connect
from .ssh_tools import resolve_ssh_credentials

logger = logging.getLogger(__name__)

# Session timeout in seconds (30 minutes)
SESSION_TIMEOUT = 1800


@dataclass
class ShellSession:
    """Active shell session with SSH PTY."""

    session_id: str
    hostname: str
    username: str
    connection: asyncssh.SSHClientConnection
    process: asyncssh.SSHClientProcess
    created_at: float
    last_activity: float
    initial_command: str | None = None


class ShellSessionManager:
    """Manages interactive shell sessions."""

    def __init__(self) -> None:
        """Initialize session manager."""
        self.sessions: dict[str, ShellSession] = {}
        self._cleanup_task: asyncio.Task[None] | None = None

    def start_cleanup_task(self) -> None:
        """Start background task to clean up expired sessions."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _cleanup_loop(self) -> None:
        """Periodically clean up expired sessions."""
        while True:
            try:
                await asyncio.sleep(60)  # Check every minute
                await self._cleanup_expired_sessions()
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    async def _cleanup_expired_sessions(self) -> None:
        """Remove sessions that have exceeded timeout."""
        now = time.time()
        expired = [
            session_id for session_id, session in self.sessions.items() if now - session.last_activity > SESSION_TIMEOUT
        ]

        for session_id in expired:
            logger.info(f"Cleaning up expired session: {session_id}")
            await self.close_session(session_id)

    async def create_session(
        self,
        hostname: str,
        username: str | None = None,
        password: str | None = None,
        port: int = 22,
        initial_command: str | None = None,
    ) -> tuple[str, ShellSession]:
        """
        Create a new interactive shell session.

        Args:
            hostname: Target host
            username: SSH username (optional, uses credentials manager)
            password: SSH password (optional, uses credentials manager)
            port: SSH port
            initial_command: Optional command to run when WebSocket connects

        Returns:
            Tuple of (session_id, ShellSession)
        """
        # Resolve credentials
        creds = resolve_ssh_credentials(
            hostname=hostname,
            username=username,
            password=password,
            port=port,
        )

        # Connect and start PTY session
        logger.info(f"Creating shell session for {creds.username}@{hostname}")
        connection = await ssh_connect(
            hostname=creds.hostname,
            username=creds.username,
            port=creds.port,
            password=creds.password,
            key_path=creds.key_path,
        )

        # Start interactive shell with PTY
        process = await connection.create_process(
            term_type="xterm-256color",
            term_size=(24, 80),  # Default size, will be updated by client
        )

        # Generate session ID
        session_id = secrets.token_urlsafe(16)

        # Create session object
        session = ShellSession(
            session_id=session_id,
            hostname=hostname,
            username=creds.username,
            connection=connection,
            process=process,
            created_at=time.time(),
            last_activity=time.time(),
            initial_command=initial_command,
        )

        self.sessions[session_id] = session
        logger.info(f"Created session {session_id} for {creds.username}@{hostname}")

        return session_id, session

    def get_session(self, session_id: str) -> ShellSession | None:
        """Get session by ID."""
        session = self.sessions.get(session_id)
        if session:
            session.last_activity = time.time()
        return session

    async def close_session(self, session_id: str) -> None:
        """Close and remove a session."""
        session = self.sessions.pop(session_id, None)
        if session:
            try:
                session.process.close()
                await session.process.wait()
                session.connection.close()
                await session.connection.wait_closed()
                logger.info(f"Closed session {session_id}")
            except Exception as e:
                logger.error(f"Error closing session {session_id}: {e}")

    async def send_input(self, session_id: str, data: str) -> None:
        """Send input to shell session."""
        session = self.get_session(session_id)
        if session and session.process.stdin:
            session.process.stdin.write(data)

    async def resize_terminal(self, session_id: str, rows: int, cols: int) -> None:
        """Resize terminal."""
        session = self.get_session(session_id)
        if session:
            session.process.change_terminal_size(cols, rows)

    async def read_output(self, session_id: str) -> str | None:
        """Read available output from session."""
        session = self.get_session(session_id)
        if session and session.process.stdout:
            try:
                # Non-blocking read
                data = await asyncio.wait_for(session.process.stdout.read(4096), timeout=0.1)
                return data if isinstance(data, str) else data.decode("utf-8")
            except TimeoutError:
                return None
            except Exception as e:
                logger.error(f"Error reading output: {e}")
                return None
        return None


# Global session manager instance
session_manager = ShellSessionManager()
