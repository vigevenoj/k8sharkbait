import ipaddress
import json
import linode
import requests
import sys
import yaml


class ClusterGenerator():
    """
    This thing poops out a cluster of linode VMs based on some configuration
    provided in a matching config.yml
    """

    def __init__(self, config='./config.yml'):
        try:
            with open(config, 'r') as f:
                configs = yaml.load(f.read())
                self._linode_token = configs['linode']['token']
                self._linode_group = configs['linode']['group']
                self._linode_region = configs['linode']['region']
                self._linode_type = configs['linode']['type']
                self._linode_distro = configs['linode']['distro']
                self._root_pass = configs['linode']['root_pass']
                self._cluster_node_count = configs['cluster']['nodes']
                self._cluster_name = configs['cluster']['name']
                self._cluster_domain = configs['cluster']['domain']
        except IOError as e:
            print("Unable to load configuration. {0}".format(e))
            sys.exit(1)
        self._client = linode.LinodeClient(self._linode_token)
        self._nodes = []  # this is a list of VMs in the cluster

    def get_cluster_nodes(self):
        """
        Fetch the existing cluster nodes from the remote API
        """
        linodes = self._client.linode.get_instances(
            linode.Linode.group == self._linode_group)
        return linodes

    def generate(self, nodes):
        """
        Create new VMs until we have filled in 1-(count) nodes for
        our cluster. Naming format is "linode-group-name-{1,2,3...}"
        The linode group name is configured via config.yml
        """
        for nodeid in range(0, self._cluster_node_count):
            print("Checking if node {0}-{1} exists".format(self._linode_group,
                                                           nodeid+1))
            try:
                if nodes[nodeid].label == "{0}-{1}".format(self._linode_group,
                                                           nodeid+1):
                    print("Node {0}-{1} already exists".format(
                        self._linode_group, nodeid+1))
                else:
                    self._create_new_node(nodeid+1)
            except IndexError:
                print("Ran out of nodes to look at...")
                self.create_new_node(nodeid+1)

    def create_new_node(self, id):
        """
        Create a new VM in the cluster, and add it to our list of existing
        nodes
        """
        print("generating new node named {0}-{1}".format(
            self._linode_group, id))
        print("and calling it {0}-{1}.{2}".format(
            self._linode_group, id, self._cluster_domain))
        l, pw = self._client.linode.create_instance(
            self._linode_type,
            self._linode_region,
            group=self._linode_group,
            distribution=self._linode_distro,
            root_pass=self._root_pass
        )
        l.label = "{0}-{1}".format(self._linode_group, id)
        print("{0} created at {2} with root password {3}".format(
            l.label, l.ipv4, pw))
        self.create_volume_for_node(l)
        print("booting the new shiny")
        l.boot()

    def generate_inventory_file(self, vms):
        """
        Persist the nodes in the cluster to disk as an ansible inventory file
        for later ansible operations
        """
        inventory_text = ""
        for vm in vms:
            public = self._get_public_address(vm.ipv4)
            print("{0}.{1} ansible_host={2}".format(
                vm.label, self._cluster_domain, public))
            inventory_text += "{0}.{1} ansible_host={2}".format(
                vm.label, self._cluster_domain, public)
        f = open("inventory", "w")
        f.write(inventory_text)
        f.close()

    def write_internal_host_vars(self, vms):
        """
        Write the internal IP addresses and hostnames for use in /etc/hosts
        on the individual nodes
        """
        output_text = ""
        for vm in vms:
            # the public and private IP addresses are not always in the same
            # order, so we have to check them :(
            address = self._get_private_address(vm.ipv4)
            print("{0}\t {1}.{2}".format(
                address, vm.label, self._cluster_domain))
            output_text += "{0}\t {1}.{2}".format(
                address, vm.label, self._cluster_domain) + '\n'
        print(output_text)
        f = open("files/internal_names", "w")
        f.write(output_text)
        f.close()

    def get_private_address(addresses):
        """
        return the first private ipv4 address of this node
        """
        for address in addresses:
            if ipaddress.ip_address(address).is_private:
                return address

    def get_public_address(addresses):
        """
        Return the first public ipv4 address of this node
        """
        for address in addresses:
            if ipaddress.ip_address(address).is_global:
                return address

    def create_volume_for_node(self, node):
        """
        Create a volume for the current node to mount, if it does not already
        exist. Attach the volume to the node if the volume already exists.
        Volumes are named {groupname}-{volumeid} where groupname is the group
        name configured via config.yml and the volumeid is a numeric identifier
        from 1 to the size of the cluster
        """
        vol = self._check_volume_for_node(node)
        if vol is None:
            # create a volume
            # This currently requires requests because the python wrapper
            # does not yet support volume creation
            # TODO: remove use of requests, switch to python api
            url = 'https://api.linode.com/v4/volumes'
            data = {'label': node.label,
                    'region': self._linode_region,
                    'size': 20}
            r = requests.post(
                url,
                data,
                headers={'Content-Type': 'application/json',
                         'Authorization': "token {0}".format(
                             self._linode_token)})
            # I can't think of anything better to do than print this
            print(r.text())
            # There should now be a volume with the same label as our node
        # Confirm the volume is attached to this node and no others
        if vol.linode != node.id:
            vol.detach()
        if vol.linode_id is None:
            vol.attach(node.id)

    def check_volume_for_node(self, node):
        """
        Check if a volume named {groupid}-{nodenumber} exists and return a
        reference to the volume or None if the volume does not exist
        """
        # check if a volume named {groupid}-{nodenumber} exists
        # return the volume or None
        volume = None
        volumes = self._client.linode.get_volumes()
        for vol in volumes:
            if volume.label == node.label:
                volume = vol
        return volume

    def check_domain(self):
        """
        Determine if the configured domain name is present in the Linode
        configuration and return either the domain object from the Linode API
        or None if the domain is not configureable via the Linode API.
        """
        domains = self._client.get_domains()
        domain = None
        for domain in domains:
            # if we don't have the domain available we can't automate this
            if domain.domain == self._cluster_domain:
                domain = domain.domain
        return domain

    def create_domain_records_for_hosts(self, nodes):
        """
        Create or update a DNS record for each host that we have created or
        updated during this run
        """
        # then that's our domain to use?
        # use same fill-in-missing logic to point subdomains
        # to the nodes.
        domain = self.check_domain()
        if domain is None:
            print("DNS is not configured for automation")
            sys.exit(1)
        for node in nodes:
            # Check if node {group}-{id} has a DNS record
            host_record = self._check_dns_for_host(node, domain.records)
            # Check if it points to the correct IP address (from inventory)
            if host_record is None:
                # Create a new record
                # TODO Use python API when it supports adding domain records
                url = "https://api.linode.com/v4/domains/{0}/records".format(
                    domain.id)
                data = {"type": "A",
                        "target": self._get_public_address(node),
                        "name": node.label}
                requests.post(
                    url,
                    data,
                    headers={'Content-Type': 'application/json',
                             'Authorization': "token {0}".format(
                                 self._linode_token)})
            else:
                # Update the record as needed
                # TODO Use python API when it supports updating domain records
                u = "https://api.linode.com/v4/domains/{0}/records/{1}".format(
                    domain.id, host_record.id)
                data = {"type": "A",
                        "target": self._get_public_address(node),
                        "name": node.label}
                requests.post(
                    u,
                    data,
                    headers={'Content-Type': 'application/json',
                             'Authorization': "token {0}".format(
                                 self._linode_token)})

    def check_dns_for_host(self, node, records):
        """
        Internal method to return a DNS record for a given host
        or None if there is no record for the specified host
        """
        host_record = None
        for record in records:
            if record.name == node.label:
                host_record = record
        return host_record

    def generate_storage_topology(self, vms):
        """
        Generate a topology.json file for Heketi to use
        """
        clusters = []
        nodes = []
        for vm in vms:
            nodes.append(self.generate_storage_node_configuration(vm))
        clusters.append({"nodes": nodes})
        topology = {"clusters": [clusters]}
        print(json.dump(topology))
        # We write this to a file so we can upload it to a node and use it in
        # the gk-deploy script. See storage.yml for details.
        f = open("files/topology.json", "w")
        f.write(json.dump(topology))
        f.close()

    def generate_storage_node_configuration(self, vm):
        entry = {"node": {
            "hostnames": {
                "manage": ["{0}.{1}".format(vm.label, self._cluster_domain)],
                "storage": [self.get_private_address(vm.ipv4)]},
            "zone": 1},
            "devices": ["/dev/sdc"]}
        return entry


if __name__ == '__main__':
    clustergenerator = ClusterGenerator()
    nodes = clustergenerator.get_cluster_nodes()
    if len(nodes) < clustergenerator._cluster_node_count:
        print(
            "We have {0} of {1} desired nodes, generating out some more".format(
                len(nodes), clustergenerator._cluster_node_count))
        clustergenerator.generate(nodes)
