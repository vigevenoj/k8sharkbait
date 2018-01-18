# What is this?
This project contains configuration to run several applications using kubernetes, and to access them from the web.
The applications are:
1. Single-serving site "whatcolorischristinashair.com"
2. The [Kanboard](https://kanboard.net/) project management software
3. [Huginn](https://github.com/cantino/huginn/)
4. [Mosquitto](https://mosquitto.org) MQTT broker
5. https://github.com/vigevenoj/owntracks-to-db


# Prerequisites
1. Admin access to a kubernetes cluster
2. The [Helm](https://helm.sh/) package manager for Kubernetes
  * `helm init`
3. A deployed StorageClass that can be used to create persistent volume claims.

If you don't have access to these prerequisites, the Preflight section has instructions on how to get a cluster bootstrapped on Linode.


# Preflight

## Cluster creation
You'll need a Linode account and a valid API token in addition to some other details in a configuration file that you should not check into source control. An example config.yaml:
```
linode:
  token: 
  # Use this to group all of the VMs used for your cluster
  group: fancy-birdbath
  # This currently depends on being in Newark for volumes, so 'us-east-1a' is required
  region: us-east-1a
  # g5-standard-1 is 2048mb ram/1vcpu, $10/month
  # g5-nanode-1 is 1024mb ram/1vcpu, $5/month
  type: g5-standard-1
  distro: linode/ubuntu17.04
  root_pass: 
  root_ssh_key: 

# Put your kubernetes cluster information here, we'll use it later
cluster:
  # This is the number of nodes in the cluster, total (including master)
  nodes: 3
  # The cluster requires a domain that has DNS configured via Linode
  domain: example.com
```
With that in place, run `python up.py` to generate your cluster nodes and ansible inventory as specified. After that, you'll need to run the `minimal-bootstrap` playbook or specify the python3 interpreter in order to run the bootstrap playbook, which will get the cluster ready for you to deploy Heketi.  

## Storage
Persistent storage is managed via 20gb volumes attached to nodes as unformatted block devices. This is handled via some internal tooling during the preflight; it has bugs and needs some human intervention. The internal tooling also generates the necessary topology.json required for Heketi to use the volumes for glusterfs.  
Once the cluster is boostrapped and Kubernetes is running, the gk-deploy.sh script from [gluster-kubernetes](https://github.com/gluster/gluster-kubernetes) and heketi-cli from [Heketi](https://github.com/heketi/heketi) must be deployed onto a node in the cluster so that they can be run from there. Running gk-deploy.sh from outside the cluster fails, see [gluster/gluseterkubernetes issue #161](https://github.com/gluster/gluster-kubernetes/issues/161) for details.  

Once storage is online, create a StorageClass to fulfill prerequisite #3. [storageclass.yaml](storageclass.yaml) will work for this.


# Deployment
## Deploy postgresql with helm:

   `helm install --name basic-database stable/postgresql`

## Deploy Traefik

   First, update the ConfigMap in traefik-configmap.yaml to include the domains you plan on managing via Traefik, as SSL is obtained via Let's Encrypt.  
   Next, ensure that a persistent volume claim exists for Traefik to store its certificate information by applying the traefik-pvc.yaml:  
   `kubectl apply -f traefik-pvc.yaml`  
   Then apply the ConfigMap you updated previously  
   `kubectl apply -f traefik-configmap.yaml`  
   ensure that Traefik has the necessary roles assigned,  
   `kubectl apply -f traefik-rbac.yaml`  

   Create a deployment for the controller:
   `kubectl apply -f traefik-ingress-controller_deployment.yaml`
## Deploy Traefik ui service

   `kubectl apply -f traefik-ui_service.yaml`  
## Deploy kanboard. 

   Our deployment uses a secret mounted in a volume for configuration to connect to the database

   `kubectl apply -f kanboard-config-secret.yaml`  
   `kubectl apply -f kanboard.yaml`  
## Configure an ingress through Traefik to Kanboard:

   `kubectl apply -f kanboard-ingress.yaml`
## Configure Huginn

   We use the [single-process](https://github.com/cantino/huginn/tree/master/docker/single-process) docker image and configuration but pass in additional configuration as environment variables to specify the local postgresql database.  
   `kubectl apply -f huginn-threaded-deployment.yaml`  
   `kubectl apply -f huginn-web-deployment.yaml`  
## Configure an ingress through Traefik to Huginn:

   `kubectl apply -f huginn-web-ingress.yaml`  

At this point Kanboard, Huginn's web interface, and Huginn's background task processing should be running in the cluster, and the web interfaces for Kanboard and Huginn should be available at the urls specified in the ingress configurations.

For a Minikube setup, use `huginn.local.ingress.yaml` and point 'hugs.sharkbaitextraordinaire.local' to the minikube IP address

## Deploy whatcolorischristinashair

   This is both a joke and the reason that this project exists. For additional details, see [whatcolorischristinashair](https://github.com/vigevenoj/whatcolorischristinashair). The deployment and service are managed via haircolor.yaml and a Traefik ingress is managed via haircolor-ingress.yaml  

   `kubectl apply -f haircolor.yaml`  
   `kubectl apply -f haircolor-ingress.yaml`  

### Updating side-loaded images that are not publicly available
   For images that are built privately and then side-loaded into the cluster, the following steps need to happen:  
   1. Build the docker image with `docker build`
   2. Save the image locally with `docker save`
   3. scp the image to the cluster nodes
   4. Load the image into the cluster nodes' local registry with `docker load`



# Future work
in no particular order
* Add inbound/outbound SMTP
* influxdb (spinning this up is underway; see the monitoring directory for helm chart values and volume claims)
* grafana (probably unneeded if a full TICK stack is used)
* secure configuration parameters
* prometheus/alertmanager or another monitoring and metrics stack (see note above about influxdb)
* mqtt (see mosquitto.yaml for this. It does not have an ingress)
* owntracks (owntracks2db pod works and is persisting data, see locationupdates.yaml)


# References
* Overview/deployment
  * https://5pi.de/2016/11/20/15-producation-grade-kubernetes-cluster/
  * http://jeremievallee.com/2017/01/31/kubernetes-with-vagrant-ansible-kubeadm/
  * http://blog.jameskyle.org/2014/08/deploying-baremetal-kubernetes-cluster/
* Storage (specifically GlusterFS/Heketi)
  * https://github.com/gluster/gluster-kubernetes/tree/master/vagrant
  * https://github.com/heketi/heketi/wiki/Kubernetes-Integration
  * http://dougbtv.com/nfvpe/2017/04/05/glusterfs-persistent/
  * http://blog.lwolf.org/post/how-i-deployed-glusterfs-cluster-to-kubernetes/
  * http://blog.lwolf.org/post/how-to-recover-data-from-broken-glusterfs-cluster/
* Ingress
  * http://containerops.org/2017/01/30/kubernetes-services-and-ingress-under-x-ray/
* Other options
  * https://blog.hypriot.com/post/setup-kubernetes-raspberry-pi-cluster/ for at home
* Linode Python API: https://github.com/linode/python-linode-api/tree/master/linode

## Notes

### Adding basic auth for an ingress
 * Create credentials with `htpasswd -Bc ingressname.auth.secret username`
 * `kubectl create secret generic ingressname-basic-auth --from-file ingressname.auth.secret`

# Troubleshooting

## Copying data from a gluster-backed volume
 * Use the `heketi-cli` API or `gluster` command (via `kubectl exec` on a glusterfs pod) to determine name of the brick where the data resides and which host that brick is on.
 * On the host where the brick is located, use `lvdisplay` to find the path of the LV where the brick is
 * Mount the device from the LV Path of `lvdisplay` somewhere, eg, /mount/mybrick
 * Copy whatever data you need from /mount/mybrick/brick/

## All gluster volumes have gone read-only
This is usually caused by an unplanned reboot of the physical hardware under the underlying host VM.  Note that the gluster logs may only indicate some sort of networking problem (connection refused to the remote bricks making up the rest of the volume) but the problem is that the process that should be listening is not running on the remote hosts.
 * Confirm that there are fewer than two processes involving gluster on the VM with `ps aux | grep gluster`
 * Delete the existing glusterfs pods and let them be re-created to resolve the issue

# Relevant bug reports
* https://github.com/kubernetes/kubernetes/issues/41141 : "Transport endpoint is not connected" results in pods with glusterfs volumes stuck in Terminating state until the node is rebooted or the mount is manually unmounted via `fusermount -uz [path to mount]`
* Heketi needs an exclusive lock on its database (boltdb). If an existing pod terminates and a new pod replaces it quickly enough, the second pod will be unable to access the database in read/write mode and will log a message that it is trying again in read-only mode. If this happens, existing volume claims will be honored but new ones cannot be created. To resolve it, scale the Heketi deployment to 0 replicas with `kubectl scale --replicas=0 deploy/heketi`, wait a few minutes, and then scale the deployment back to 1 replica with `kubectl scale --replicas=1 deploy/heketi` and then watch its logs to confirm Heketi started up in read/write mode. See https://github.com/gluster/gluster-kubernetes/issues/257 for some additional details
