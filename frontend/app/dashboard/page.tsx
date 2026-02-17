'use client'

import { useEffect, useState, Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import axios from 'axios'

// Use relative URLs so Next.js rewrites handle API routing
const API_BASE = '/api'

// Force dynamic rendering to avoid useSearchParams static generation issues
export const dynamic = 'force-dynamic'

export default function Dashboard() {
  return (
    <Suspense fallback={<div className="max-w-4xl mx-auto px-4 py-16 text-center">
      <div className="animate-spin text-4xl mb-4">⚙️</div>
      <p className="text-gray-600">Loading...</p>
    </div>}>
      <DashboardContent />
    </Suspense>
  )
}

function DashboardContent() {
  const searchParams = useSearchParams()
  const projectId = searchParams.get('project')
  
  const [status, setStatus] = useState<any>(null)
  const [assets, setAssets] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!projectId) return

    const fetchStatus = async () => {
      try {
        const response = await axios.get(`${API_BASE}/processing/status/${projectId}/`)
        setStatus(response.data)
        
        if (response.data.status === 'completed') {
          const assetsResponse = await axios.get(`${API_BASE}/projects/${projectId}/assets/`)
          setAssets(assetsResponse.data.assets)
          setLoading(false)
        } else if (response.data.status === 'failed') {
          setLoading(false)
        }
      } catch (error) {
        console.error('Error fetching status:', error)
      }
    }

    fetchStatus()
    const interval = setInterval(fetchStatus, 5000) // Poll every 5 seconds
    
    return () => clearInterval(interval)
  }, [projectId])

  if (!projectId) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-16 text-center">
        <h1 className="text-2xl font-bold text-gray-900">No project selected</h1>
        <p className="mt-2 text-gray-600">Upload a video to get started</p>
      </div>
    )
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold text-gray-900 mb-8">Processing Dashboard</h1>
      
      {/* Status Card */}
      <div className="bg-white rounded-lg shadow p-6 mb-8">
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="text-sm text-gray-500">Project ID</p>
            <p className="font-mono text-sm">{projectId}</p>
          </div>
          <StatusBadge status={status?.status} />
        </div>
        
        {status && (
          <>
            <div className="w-full bg-gray-200 rounded-full h-3 mb-2">
              <div
                className="bg-primary-600 h-3 rounded-full transition-all duration-500"
                style={{ width: `${status.progress_percent}%` }}
              />
            </div>
            <p className="text-sm text-gray-600">
              {status.processing_stage || 'Initializing...'}
            </p>
          </>
        )}
      </div>

      {/* Assets Grid */}
      {assets.length > 0 && (
        <div>
          <h2 className="text-xl font-semibold mb-4">Generated Assets ({assets.length})</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {assets.map((asset) => (
              <AssetCard key={asset.id} asset={asset} />
            ))}
          </div>
        </div>
      )}

      {loading && assets.length === 0 && (
        <div className="text-center py-12">
          <div className="animate-spin text-4xl mb-4">⚙️</div>
          <p className="text-gray-600">Processing your video...</p>
          <p className="text-sm text-gray-500 mt-2">This usually takes 5-10 minutes</p>
        </div>
      )}
    </div>
  )
}

function StatusBadge({ status }: { status?: string }) {
  const styles: Record<string, string> = {
    pending: 'bg-yellow-100 text-yellow-800',
    processing: 'bg-blue-100 text-blue-800',
    completed: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800',
  }

  return (
    <span className={`px-3 py-1 rounded-full text-sm font-medium ${styles[status || 'pending']}`}>
      {status || 'pending'}
    </span>
  )
}

function AssetCard({ asset }: { asset: any }) {
  const isVideo = asset.asset_type?.includes('video')
  
  return (
    <div className="bg-white rounded-lg shadow overflow-hidden">
      {isVideo ? (
        <div className="aspect-video bg-gray-900 flex items-center justify-center">
          <span className="text-4xl">🎬</span>
        </div>
      ) : (
        <div className="aspect-video bg-gray-100 p-4 flex items-center justify-center">
          <p className="text-sm text-gray-600 line-clamp-4">{asset.content || asset.title}</p>
        </div>
      )}
      
      <div className="p-4">
        <h3 className="font-semibold text-sm mb-1 truncate">{asset.title}</h3>
        <p className="text-xs text-gray-500 mb-3">{asset.asset_type}</p>
        
        {asset.file_url ? (
          <a
            href={asset.file_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary-600 text-sm hover:underline"
          >
            Download →
          </a>
        ) : asset.content ? (
          <span className="text-green-600 text-sm">✓ Ready</span>
        ) : (
          <span className="text-gray-400 text-sm">Processing...</span>
        )}
      </div>
    </div>
  )
}
