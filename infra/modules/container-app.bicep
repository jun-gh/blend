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

@description('Optional site access password')
@secure()
param sitePassword string = ''

@description('Scale-to-zero: set minReplicas=0')
param minReplicas int = 0

param maxReplicas int = 5

@description('Gemini chat model')
param geminiChatModel string = 'models/gemini-3.1-flash-lite'

@description('Gemini embedding model')
param geminiEmbedModel string = 'models/gemini-embedding-2'

@description('Embedding dimensionality')
param embeddingDimensions int = 3072

@description('Dense search weight')
param denseWeight string = '0.6'

@description('Sparse search weight')
param sparseWeight string = '0.4'

@description('Top-K candidate chunks retrieved before fusion')
param topKRetrieval string = '10'

@description('Top-K chunks sent to Gemini LLM context window')
param topKContext string = '5'

@description('Days before session and documents expire')
param sessionExpiryDays int = 7

@description('Maximum documents allowed per session')
param maxDocumentsPerSession int = 10

@description('Allowed CORS origins (comma-separated domains or single domain URL)')
param corsOrigins string = 'https://blend-jmco.vercel.app'

var allowedOrigins = split(corsOrigins, ',')

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
          allowedOrigins: allowedOrigins
          allowedMethods: ['GET', 'POST', 'DELETE', 'OPTIONS']
          allowedHeaders: ['*']
        }
      }
      secrets: [
        { name: 'gemini-api-key', value: geminiApiKey }
        { name: 'database-url',   value: databaseUrl }
        { name: 'site-password',  value: empty(sitePassword) ? 'none' : sitePassword }
      ]
    }
    template: {
      containers: [
        {
          name: 'blend-api'
          image: containerImage
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            { name: 'GEMINI_API_KEY', secretRef: 'gemini-api-key' }
            { name: 'DATABASE_URL',   secretRef: 'database-url' }
            { name: 'SITE_PASSWORD',  secretRef: 'site-password' }
            { name: 'GEMINI_CHAT_MODEL',    value: geminiChatModel }
            { name: 'GEMINI_EMBED_MODEL',   value: geminiEmbedModel }
            { name: 'EMBEDDING_DIMENSIONS', value: string(embeddingDimensions) }
            { name: 'DENSE_WEIGHT',         value: denseWeight }
            { name: 'SPARSE_WEIGHT',        value: sparseWeight }
            { name: 'TOP_K_RETRIEVAL',      value: topKRetrieval }
            { name: 'TOP_K_CONTEXT',        value: topKContext }
            { name: 'SESSION_EXPIRY_DAYS',  value: string(sessionExpiryDays) }
            { name: 'MAX_DOCUMENTS_PER_SESSION', value: string(maxDocumentsPerSession) }
            { name: 'DEBUG',          value: 'false' }
            { name: 'CORS_ORIGINS',   value: corsOrigins }
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
