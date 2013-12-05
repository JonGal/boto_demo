#Boto demo adpated from  source found on github
# Creates an Elastic Load Balancer, Launch Confguration, 
# Scaling Group, and Scaling Policies using the boto library for python
#
# In order to run this you should either run on an EC2 instance with appropriate IAM Role
# or create a file for system users or individiuals to access the proper access credentials
# Use /etc/boto.cfg - for site-wide settings that all users on this machine will use
# Use ~/.boto - for user-specific settings
#
# Inside this file, make sure you have stored the proper credntials, in this format:
#
#[Credentials]
#aws_access_key_id = <your access key>
#aws_secret_access_key = <your secret key>
#
#See this post for information on how to get your credentials:
# http://blogs.aws.amazon.com/security/post/Tx1R9KDN9ISZ0HF/Where-s-my-secret-access-key

import sys, getopt
import boto.ec2
 
from boto.ec2.elb import ELBConnection
from boto.ec2.elb import HealthCheck
 
from boto.ec2.autoscale import AutoScaleConnection
from boto.ec2.autoscale import LaunchConfiguration
from boto.ec2.autoscale import AutoScalingGroup
from boto.ec2.autoscale import ScalingPolicy

##############################CONFIGURATION#######################################

 
region = 'us-east-1' #The region you want to connect to
#region = 'us-west-1' #The region you want to connect to
 
try:
    opts, args = getopt.getopt(sys.argv[1:],"r:",["region="])
except getopt.GetoptError:
    print 'bare_elp.py -r <AWS Region>'
    sys.exit(2)

for opt, arg in opts:
    if opt == '-h':
        print 'bare_elb.py -r <AWS Region>'
        sys.exit()
    elif opt in ("-r", "--region"):
        region = arg

print 'Region file is ', region

#Set up the correct region and regional endpoint
connect_region = boto.ec2.regioninfo.RegionInfo(name=region,
    endpoint="ec2."+region+".amazonaws.com")


elastic_load_balancer = {
    'name': 'NDH-boto-demo-lb',#The name of your load balancer
    'health_check_target': 'HTTP:80/index.html',#Location to perform health checks
    #'connection_forwarding': [(80, 80, 'http'), (443, 443, 'tcp')],#[Load Balancer Port, EC2 Instance Port, Protocol]
    'connection_forwarding': [(80, 80, 'http') ],#[Load Balancer Port, EC2 Instance Port, Protocol]
    'timeout': 3, #Number of seconds to wait for a response from a ping
    'interval': 20 #Number of seconds between health checks
}
 
 
 
#=================AMI to launch======================================================
as_ami = {
    #'id': 'ami-02cee847', #The AMI ID of the instance your Auto Scaling group will launch - BitNAMI LAMP us-west-1
    'id': 'ami-022a946b', #The AMI ID of the instance your Auto Scaling group will launch - Bitnami LAMP us-east-1
    'access_key': 'YOUR ACCESS KEY', #The key the EC2 instance will be configured with
    'security_groups': ["YPUR SECURITY GROUP"], #The security group(s) your instances will belong to 
    'instance_type': 'm1.small', #The size of instance that will be launched
    'instance_monitoring': True, #Indicated whether the instances will be launched with detailed monitoring enabled. Needed to enable CloudWatch
    'instance_profile_arn': 'arn:aws:iam::323826331358:instance-profile/THE-NAME-OF-ROLE' #ARN of IAM Role
}

if region == 'us-west-1':
	as_ami['id'] = 'ami-02cee847'
if region == 'us-west-2':
	as_ami['id'] ='ami-f94ddbc9'


 
##############################END CONFIGURATION#######################################
 
#=================Construct a list of all availability zones for your region=========

get_reg = boto.ec2.connect_to_region(region_name=region )
    
print get_reg
zones = get_reg.get_all_zones()
 

zoneStrings = []
for zone in zones:
    zoneStrings.append(zone.name)

print zoneStrings;

#==== Connect to the EC2 services =============
conn_reg = boto.ec2.connection.EC2Connection(region=connect_region)


#=========Start Instances =============
instance_ids = []
for name in zoneStrings:
	if name == 'us-east-1a':
		continue

	reg = conn_reg.run_instances (as_ami['id'],
		key_name=as_ami['access_key'],
		placement=name,
		instance_type=as_ami['instance_type'],
		security_groups=as_ami['security_groups'],
		monitoring_enabled=as_ami['instance_monitoring'],
		instance_profile_arn=as_ami['instance_profile_arn']
		)
	instance_ids.append(reg.instances[0].id)

print instance_ids;

#==== Connect to the ELB services =============
#Set up the correct region and regional endpoint
elb_connect_region = boto.ec2.regioninfo.RegionInfo(name=region,
    endpoint="elasticloadbalancing."+region+".amazonaws.com")
conn_elb = ELBConnection(region=elb_connect_region)


##=================Create a Load Balancer=============================================
#For a complete list of options see http://boto.cloudhackers.com/ref/ec2.html#module-boto.ec2.elb.healthcheck
hc = HealthCheck('healthCheck',
                     interval=elastic_load_balancer['interval'],
                     target=elastic_load_balancer['health_check_target'],
                     timeout=elastic_load_balancer['timeout'])
# 
##For a complete list of options see http://boto.cloudhackers.com/ref/ec2.html#boto.ec2.elb.ELBConnection.create_load_balancer
lb = conn_elb.create_load_balancer(elastic_load_balancer['name'],
                                       sorted(zoneStrings, reverse=True),
                                       elastic_load_balancer['connection_forwarding'])
 
lb.configure_health_check(hc)
lb.register_instances(instance_ids)
# 
##DNS name for your new load balancer
print "Map the CNAME of your website to: %s" % (lb.dns_name)
#=================Create a Auto Scaling Group and a Launch Configuration=============================================
#For a complete list of options see http://boto.cloudhackers.com/ref/ec2.html#boto.ec2.autoscale.launchconfig.LaunchConfiguration
lc = LaunchConfiguration(name=lc_name, image_id=as_ami['id'],
                             key_name=as_ami['access_key'],
                             security_groups=as_ami['security_groups'],
                             instance_type=as_ami['instance_type'],
                             instance_monitoring=as_ami['instance_monitoring'])
conn_as.create_launch_configuration(lc)

#For a complete list of options see http://boto.cloudhackers.com/ref/ec2.html#boto.ec2.autoscale.group.AutoScalingGroup
ag = AutoScalingGroup(group_name=autoscaling_group['name'], load_balancers=[elastic_load_balancer['name']],
                          availability_zones=zoneStrings,
                          launch_config=lc, min_size=autoscaling_group['min_size'], max_size=autoscaling_group['max_size'])
conn_as.create_auto_scaling_group(ag)


#=================Create Scaling Policies=============================================
#Policy for scaling the number of servers up and down
#For a complete list of options see http://boto.cloudhackers.com/ref/ec2.html#boto.ec2.autoscale.policy.ScalingPolicy
scalingUpPolicy = ScalingPolicy(name='webserverScaleUpPolicy',
                                  adjustment_type='ChangeInCapacity',
                                  as_name=ag.name,
                                  scaling_adjustment=2)

scalingDownPolicy = ScalingPolicy(name='webserverScaleDownPolicy',
                                  adjustment_type='ChangeInCapacity',
                                  as_name=ag.name,
                                  scaling_adjustment=-1,
                                  cooldown=180)

conn_as.create_scaling_policy(scalingUpPolicy)
conn_as.create_scaling_policy(scalingDownPolicy)
