VAGRANTFILE_API_VERSION = "2"


$script = <<SCRIPT

apt-get update
apt-get install git curl python-pip redis-server libffi-dev python-dev -y libssl-dev

git clone https://github.com/gleicon/restmq.git
cd restmq
pip install -e .

cd start_scripts
touch acl.conf
bash restmq_server --acl=acl.conf --listen=0.0.0.0 &

SCRIPT

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|
  config.vm.box = "hashicorp/precise32"
  config.vm.provision "shell", inline: $script
  config.vm.network "forwarded_port", guest: 8888, host: 8888
end
