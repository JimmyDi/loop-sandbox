import os

import docker

PREFIX = "loop-sandbox-"


def daemon():
    return docker.from_env()


def cleanup(rec):
    client = daemon()
    try:
        try:
            client.containers.get(rec["container"]).remove(force=True)
        except docker.errors.NotFound:
            pass
        try:
            network = client.networks.get(rec["network"])
            disconnect(network)
            network.remove()
        except docker.errors.NotFound:
            pass
    finally:
        client.close()


def provision(sid, token):
    client = daemon()
    network = None
    container = None
    try:
        network = client.networks.create(
            PREFIX + sid,
            driver="bridge",
            internal=os.getenv("ALLOW_EGRESS", "0") != "1",
            labels={"loop-sandbox.owner": "local"},
        )
        controller = client.containers.get(os.getenv("CONTROLLER_CONTAINER", "loop-sandbox-api"))
        network.connect(controller)
        container = client.containers.run(
            os.getenv("WORKER_IMAGE", "loop-sandbox-worker:local"),
            name=PREFIX + sid,
            detach=True,
            network=network.name,
            environment={"WORKER_TOKEN": token},
            labels={"loop-sandbox.owner": "local"},
            mem_limit="1g",
            nano_cpus=1_000_000_000,
            pids_limit=256,
            read_only=True,
            tmpfs={
                "/tmp": "rw,nosuid,nodev,size=256m",
                "/workspace": "rw,nosuid,nodev,size=128m,mode=1777",
            },
            cap_drop=["ALL"],
            security_opt=["no-new-privileges:true"],
            shm_size="256m",
            init=True,
        )
        return {
            "container": container.id,
            "network": network.name,
            "url": "http://" + container.name + ":8000",
            "token": token,
        }
    except Exception:
        if container:
            container.remove(force=True)
        if network:
            disconnect(network)
            network.remove()
        raise
    finally:
        client.close()


def sweep():
    client = daemon()
    try:
        for container in client.containers.list(
            all=True, filters={"label": "loop-sandbox.owner=local"}
        ):
            container.remove(force=True)
        for network in client.networks.list(filters={"label": "loop-sandbox.owner=local"}):
            disconnect(network)
            network.remove()
    finally:
        client.close()


def disconnect(network):
    try:
        network.disconnect(os.getenv("CONTROLLER_CONTAINER", "loop-sandbox-api"), force=True)
    except docker.errors.APIError as error:
        if error.status_code != 404 and "is not connected" not in str(error):
            raise


def is_running(rec):
    """Only a confirmed missing/stopped container permits automatic replacement."""
    client = daemon()
    try:
        try:
            return client.containers.get(rec["container"]).status == "running"
        except docker.errors.NotFound:
            return False
    finally:
        client.close()
