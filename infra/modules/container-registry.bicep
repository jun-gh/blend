// ─────────────────────────────────────────────────────────────────────────────
// Module: Container Registry (Azure Container Registry – optional)
// Note: The primary CI/CD pipeline uses GHCR (GitHub Container Registry).
// This module provisions an ACR as an alternative / enterprise registry.
// ─────────────────────────────────────────────────────────────────────────────

@description('ACR name (must be globally unique, alphanumeric)')
param name string

@description('Azure region')
param location string

@description('Resource tags')
param tags object

@description('SKU for ACR (Basic | Standard | Premium)')
@allowed(['Basic', 'Standard', 'Premium'])
param sku string = 'Basic'

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: name
  location: location
  tags: tags
  sku: { name: sku }
  properties: {
    adminUserEnabled: false   // Use managed identity / OIDC instead
    publicNetworkAccess: 'Enabled'
    zoneRedundancy: 'Disabled'
  }
}

output loginServer string = acr.properties.loginServer
output resourceId string = acr.id
