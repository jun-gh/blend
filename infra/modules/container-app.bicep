// ─────────────────────────────────────────────────────────────────
// Module: Blend API Container App
// ─────────────────────────────────────────────────────────────────

@description('Container App name')
param name string

@description('Azure region')
param location string

@description('Resource tags')
param tags object

@description('Container Apps Environment resource ID')
param environmentId string

@description('Container image to deploy')
param containerImage string

@secure()
param geminiApiKey string

@secure()
param databaseUrl string

@description('Scale-to-zero: set minReplicas=0')
param minReplicas int = 0

param maxReplicas int = 5

resource ca 'Microsoft.App/containerApps@2024-03-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    environmentId: environmentId
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
        corsPolicy: {
          allowedOrigins: ['*']
          allowedMethods: ['GET', 'POST', 'DELETE', 'OPTIONS']
          allowedHeaders: ['*']
        }
      }
      secrets: [
        { name: 'gemini-api-key', value: geminiApiKey }
        { name: 'database-url',   value: databaseUrl }
      ]
    }
    template: {
      containers: [
        {
          name: 'blend-api'
          image: containerImage
          resources: {
            cpu:    '0.5'
            memory: '1Gi'
          }
          env: [
            { name: 'GEMINI_API_KEY', secretRef: 'gemini-api-key' }
            { name: 'DATABASE_URL',   secretRef: 'database-url' }
            { name: 'DEBUG',          value: 'false' }
            { name: 'CORS_ORIGINS',   value: '*' }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: { path: '/health/', port: 8000, scheme: 'HTTP' }
              initialDelaySeconds: 10
              periodSeconds: 30
            }
            {
              type: 'Readiness'
              httpGet: { path: '/health/', port: 8000, scheme: 'HTTP' }
              initialDelaySeconds: 5
              periodSeconds: 10
            }
          ]
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
        rules: [
          {
            name: 'http-scaling'
            http: { metadata: { concurrentRequests: '20' } }
          }
        ]
      }
    }
  }
}

output fqdn string = ca.properties.configuration.ingress.fqdn
output name string = ca.name
