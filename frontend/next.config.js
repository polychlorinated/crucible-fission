/** @type {import('next').NextConfig} */
const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const baseUrl = apiUrl.startsWith('http') ? apiUrl : `https://${apiUrl}`

const nextConfig = {
  // Prevent trailing slash redirects that convert POST to GET
  trailingSlash: false,
  
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${baseUrl}/api/:path*`
      }
    ]
  }
}

module.exports = nextConfig
