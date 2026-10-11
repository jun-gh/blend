// ─────────────────────────────────────────────────────────────────
// Blend – Azure infrastructure (Bicep)
// Deploys:
//   • Azure Container Apps Environment
//   • Blend API Container App (scale-to-zero)
// Container images are pulled from GHCR (GitHub Container Registry)
// ─────────────────────────────────────────────────────────────────

targetScope = 'resourceGroup'

@description('Azure region for all resources')
param location string = resourceGroup().location

@description('Environment tag (dev | staging | prod)')
@allowed(['dev', 'staging', 'prod'])
param environmentName string = 'prod'

@description('Full container image tag, e.g. ghcr.io/org/blend-backend:sha-abc1234')
param containerImage string

@description('Gemini API key – supplied from GitHub Actions secrets')
@secure()
param geminiApiKey string

@description('Database connection URL')
@secure()
param databaseUrl string

@description('Minimum replicas (0 = scale-to-zero)')
param minReplicas int = 0

@description('Maximum replicas')
param maxReplicas int = 5

@description('Optional ID of an existing Container Apps Environment to reuse')
param existingEnvironmentId string = ''

@description('Location for the Container App (must match the Container Apps Environment region if reusing one)')
param appLocation string = location

var appName = 'blend'
var tags = {
  application: appName
  environment: environmentName
  managedBy: 'bicep'
}

// ─── Log Analytics workspace (only created if no existing environment provided) ──
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = if (empty(existingEnvironmentId)) {
  name: 'log-${appName}-${environmentName}'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

// ─── Container Apps Environment (only created if no existing environment provided) 
resource caEnv 'Microsoft.App/managedEnvironments@2024-03-01' = if (empty(existingEnvironmentId)) {
  name: 'cae-${appName}-${environmentName}'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: empty(existingEnvironmentId) ? logAnalytics!.properties.customerId : ''
        sharedKey: empty(existingEnvironmentId) ? logAnalytics!.listKeys().primarySharedKey : ''
      }
    }
  }
}

var targetEnvId = empty(existingEnvironmentId) ? caEnv.id : existingEnvironmentId

// ─── Container App Modules ────────────────────────────────────────
module containerApp 'modules/container-app.bicep' = {
  name: 'deploy-blend-api'
  params: {
    name: '${appName}-api'
    location: appLocation
    tags: tags
    environmentId: targetEnvId
    containerImage: containerImage
    geminiApiKey: geminiApiKey
    databaseUrl: databaseUrl
    minReplicas: minReplicas
    maxReplicas: maxReplicas
  }
}

// ─── Outputs ──────────────────────────────────────────────────────
output containerAppFqdn string = containerApp.outputs.fqdn
output containerAppName string = containerApp.outputs.name
