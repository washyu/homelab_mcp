FROM ubuntu:22.04

# Set non-interactive frontend to avoid prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install SSH server and sudo
RUN apt-get update && \
    apt-get install -y \
        openssh-server \
        sudo \
        curl \
        net-tools \
        iproute2 \
        procps \
        vim \
        && \
    rm -rf /var/lib/apt/lists/*

# Create SSH directory and configure SSH
RUN mkdir /var/run/sshd && \
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config && \
    sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config

# Create test admin user with passwordless sudo
RUN useradd -m -s /bin/bash -G sudo testadmin && \
    echo 'testadmin:testpass123' | chpasswd && \
    echo 'testadmin ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/testadmin

# Create a regular test user (optional)
RUN useradd -m -s /bin/bash testuser && \
    echo 'testuser:userpass123' | chpasswd

# Set root password for testing
RUN echo 'root:rootpass123' | chpasswd

# Expose SSH port
EXPOSE 22

# Start SSH service
CMD ["/usr/sbin/sshd", "-D"]
