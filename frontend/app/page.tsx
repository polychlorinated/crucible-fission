'use client'

import { useState } from 'react'
import axios from 'axios'

// Use relative URLs so Next.js rewrites handle API routing
const API_BASE = '/api'

export default function Home() {
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [projectId, setProjectId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0])
      setError(null)
    }
  }

  const handleUpload = async () => {
    if (!file) return

    setUploading(true)
    setUploadProgress(0)

    const formData = new FormData()
    formData.append('file', file)
    formData.append('content_type', 'testimonial')

    try {
      const response = await axios.post(`${API_BASE}/upload`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total) {
            const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total)
            setUploadProgress(progress)
          }
        },
      })

      setProjectId(response.data.project_id)
      window.location.href = `/dashboard?project=${response.data.project_id}`
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Upload failed. Please try again.')
      setUploading(false)
    }
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-16">
      <div className="text-center mb-12">
        <h1 className="text-4xl font-bold text-gray-900 mb-4">
          Crucible Fission Reactor
        </h1>
        <p className="text-xl text-gray-600">
          Transform one video into 50+ content assets
        </p>
      </div>

      <div className="bg-white rounded-lg shadow-lg p-8">
        <div className="border-2 border-dashed border-gray-300 rounded-lg p-12 text-center hover:border-primary-500 transition-colors">
          <input
            type="file"
            accept="video/*"
            onChange={handleFileChange}
            className="hidden"
            id="video-upload"
          />
          <label
            htmlFor="video-upload"
            className="cursor-pointer block"
          >
            <div className="text-6xl mb-4">📹</div>
            <p className="text-lg text-gray-700 mb-2">
              {file ? file.name : 'Drop your video here or click to browse'}
            </p>
            <p className="text-sm text-gray-500">
              Supports MP4, MOV, AVI up to 500MB
            </p>
          </label>
        </div>

        {file && !uploading && (
          <div className="mt-6 text-center">
            <button
              onClick={handleUpload}
              className="bg-primary-600 text-white px-8 py-3 rounded-lg font-semibold hover:bg-primary-700 transition-colors"
            >
              🚀 Start Fission Process
            </button>
          </div>
        )}

        {uploading && (
          <div className="mt-6">
            <div className="w-full bg-gray-200 rounded-full h-4">
              <div
                className="bg-primary-600 h-4 rounded-full transition-all duration-300"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
            <p className="text-center mt-2 text-gray-600">
              Uploading... {uploadProgress}%
            </p>
          </div>
        )}

        {error && (
          <div className="mt-4 p-4 bg-red-50 text-red-700 rounded-lg">
            {error}
          </div>
        )}
      </div>

      <div className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-6">
        <FeatureCard
          icon="⚡"
          title="Fast Processing"
          description="10-minute turnaround for 30-minute videos"
        />
        <FeatureCard
          icon="🎯"
          title="AI-Powered"
          description="Kimi identifies your best moments automatically"
        />
        <FeatureCard
          icon="📦"
          title="50+ Assets"
          description="Videos, quotes, emails, and social posts"
        />
      </div>
    </div>
  )
}

function FeatureCard({ icon, title, description }: { icon: string; title: string; description: string }) {
  return (
    <div className="bg-white rounded-lg shadow p-6 text-center">
      <div className="text-4xl mb-3">{icon}</div>
      <h3 className="font-semibold text-lg mb-2">{title}</h3>
      <p className="text-gray-600 text-sm">{description}</p>
    </div>
  )
}
