# What is this?
This project contains configuration to run several applications using kubernetes, and to access them from the web
The applications are:
1. The [Kanboard](https://kanboard.net/) project management software
2. [Huginn](https://github.com/cantino/huginn/)

They are backed by a postgres database and ingress is configured and tracked via [Traefik](https://traefik.io/)

# Prerequisites
1. Admin access to a kubernetes cluster
2. The [Helm](https://helm.sh/) package manager for Kubernetes


# Deployment
* Deploy postgresql with helm:

   `helm install stable/postgresql`
* Deploy Traefik

   `kubectl apply -f traefik-ingress-controller_deployment.yaml`
* Deploy Traefik ui service

   `kubectl apply -f traefik-ui_service.yaml`
* Deploy kanboard. The configuration is missing the database information

   `kubectl apply -f kanboard-deployment.yaml`
   `kubectl apply -f kanboard-service.yaml`
* Configure an ingress through Traefik to Kanboard:

   `kubectl apply -f kanboard-ingress.yaml`
* Configure Huginn

   We use the [single-process](https://github.com/cantino/huginn/tree/master/docker/single-process) docker image and configuration but pass in additional configuration as environment variables to specify the local postgresql database.
   `kubectl apply -f huginn-threaded-deployment.yaml`
   `kubectl apply -f huginn-threaded-service.yaml`
   `kubectl apply -f huginn-web-deployment.yaml`
   `kubectl apply -f huginn-web-service.yaml`
* Configure an ingress through Traefik to Huginn:

   `kubectl apply -f huginn-web-ingress.yaml`

At this point Kanboard, Huginn's web interface, and Huginn's background task processing should be running in the cluster, and the web interfaces for Kanboard and Huginn should be available at the urls specified in the ingress configurations.
