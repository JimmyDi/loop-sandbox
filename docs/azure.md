# Run on an Azure Linux VM

Use an Ubuntu 24.04 x86_64 VM. Start with 4 vCPUs and 8 GiB of memory; consider 16 GiB for concurrent browser workloads. Install Docker Engine, Compose, Python 3, and Git.

1. Create a personal VM or reuse an existing one, and sign in with an SSH key.
2. Restrict NSG access to port 22 from your current source IP. Do not expose API or worker ports publicly.
3. Transfer the repository to the VM and follow the README build and smoke-test instructions.
4. Connect through a local SSH tunnel:

~~~bash
ssh -N -L 8080:127.0.0.1:8080 azureuser@<vm-ip>
~~~

Send local requests to http://127.0.0.1:8080 using the token generated in the VM's private .loop-sandbox/credentials.json. When running smoke.py locally, supply the VM API key through DEMO_API_KEY. Configure model credentials on the VM.

## Publish images

You can push images to ACR, pull them on the VM, and set WORKER_IMAGE. The controller uses locally available images; it does not handle registry login or automatic image pulls. You can also publish the API image and replace the Compose build setting with image.

~~~bash
az acr login --name <registry-name>
docker tag loop-sandbox-worker:local <registry-name>.azurecr.io/loop-sandbox-worker:v1
docker push <registry-name>.azurecr.io/loop-sandbox-worker:v1
~~~

## Migrate to managed containers

This project requires the Docker socket. The same deployment cannot run unchanged on managed container platforms without host Docker access. ACI/AKS support requires a new provider for cloud resource creation and deletion, private addressing, persistent leases and ownership, resource state management, retries and orphan scans, network policy, and artifact storage. This adaptation is not implemented.

VMs, disks, and registries may incur charges. Download artifacts and remove dedicated experiment resources when finished. This repository does not automatically create Azure resources.
