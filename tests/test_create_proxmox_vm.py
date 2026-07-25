import pytest
from mcp_test_framework.test_code import ToolCallError, mcp_session, tool

from tests.test_code._generated.homelab_mcp import (
    CreateProxmoxVmParams,
    DeleteProxmoxVmParams,
    GetProxmoxVmStatusParams,
)


@pytest.mark.asyncio(loop_scope="session")
async def test_is_create_vm_visable(mcp_session):
    tools = await mcp_session.list_tools()
    assert any(t.name == "create_proxmox_vm" for t in tools)


@pytest.mark.asyncio(loop_scope="session")
async def test_create_vm(mcp_session):
    node = "pve"
    vmid = 9004
    host = "192.168.10.20"
    name = "test-vm"

    # Pre-flight cleanup: if a VM with this id already exists, remove it so the
    # create below starts from a clean slate. get_proxmox_vm_status raises
    # ToolCallError when the VM is absent (the server maps a status:"error"
    # payload to MCP isError=True), which is the "nothing to clean up" path.
    get_vm_params = GetProxmoxVmStatusParams(node=node, vmid=vmid, host=host)
    try:
        get_response = await tool("get_proxmox_vm_status").call(get_vm_params)
    except ToolCallError:
        pass  # No VM with this id -- nothing to delete.
    else:
        # A VM with this id exists. Only delete it when it's our test-vm so we
        # never clobber an unrelated VM that happens to share the id.
        existing_name = (get_response.data or {}).get("data", {}).get("name")
        assert existing_name == name, (
            f"VM {vmid} already exists but is named {existing_name!r}, not "
            f"{name!r}; refusing to delete an unrelated VM."
        )
        delete_params = DeleteProxmoxVmParams(
            node=node,
            vmid=vmid,
            host=host,
            purge=True,
        )
        delete_response = await tool("delete_proxmox_vm").call(delete_params)
        assert delete_response.is_error is False, f"Failed to delete existing VM {vmid}: {delete_response.data}"

    create_params = CreateProxmoxVmParams(
        vmid=vmid,
        node=node,
        name=name,
        cores=1,
        memory=512,
        host=host,
    )
    response = await tool("create_proxmox_vm").call(create_params)
    assert response.is_error is False
    print(response.data)

    # Confirm the VM is now present with the expected name.
    verify_response = await tool("get_proxmox_vm_status").call(get_vm_params)
    assert verify_response.is_error is False
    created_name = (verify_response.data or {}).get("data", {}).get("name")
    assert created_name == name, f"VM {vmid} not found with expected name {name!r} after create; got {created_name!r}."
