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

var appName = 'blend'
var tags = {
  application: appName
  environment: environmentName
  managedBy: 'bicep'
}

// ─── Log Analytics workspace ──────────────────────────────────────
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: 'log-${appName}-${environmentName}'
  location: location
  tags: tags
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

// ─── Container Apps Environment ───────────────────────────────────
resource caEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'cae-${appName}-${environmentName}'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
}

// ─── Container App Modules ────────────────────────────────────────
module containerApp 'modules/container-app.bicep' = {
  name: 'deploy-blend-api'
  params: {
    name: '${appName}-api'
    location: location
    tags: tags
    environmentId: caEnv.id
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
