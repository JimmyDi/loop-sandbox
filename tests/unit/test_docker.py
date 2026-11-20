from unittest.mock import patch

from loop_sandbox.runtime import docker as provider


def test_cleanup_disconnects_controller_before_network_remove():
    events = []

    class Network:
        def disconnect(self, name, force):
            events.append("disconnect")

        def remove(self):
            events.append("remove-network")

    class Container:
        def remove(self, force):
            events.append("remove-container")

    class Access:
        def __init__(self, value):
            self.value = value

        def get(self, name):
            return self.value

    class Client:
        networks = Access(Network())
        containers = Access(Container())

        def close(self):
            pass

    with patch.object(provider, "daemon", return_value=Client()):
        provider.cleanup({"container": "worker", "network": "private"})
    assert events == ["remove-container", "disconnect", "remove-network"]
