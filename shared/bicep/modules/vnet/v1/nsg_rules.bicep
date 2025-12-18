@export()
@description('Network Security Group Security Rule: Deny all inbound traffic')
var nsgsr_denyAllInbound = {
  name: 'DenyAllInbound'
  properties: {
    description: 'Deny all inbound traffic'
    protocol: '*'
    sourcePortRange: '*'
    destinationPortRange: '*'
    sourceAddressPrefix: '*'
    destinationAddressPrefix: '*'
    access: 'Deny'
    priority: 4096
    direction: 'Inbound'
  }
}
