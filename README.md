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

Configure an ingress through Traefik to Kanboard:

   `kubectl apply -f kanboard-ingress.yaml`

