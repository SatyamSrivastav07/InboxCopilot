const HOP_BY_HOP_HEADERS = new Set([
  'connection',
  'content-length',
  'host',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'te',
  'trailer',
  'transfer-encoding',
  'upgrade',
])

export const config = {
  api: {
    bodyParser: false,
  },
}

function backendOrigin() {
  const value = process.env.BACKEND_ORIGIN
  if (!value) {
    throw new Error('BACKEND_ORIGIN is not configured.')
  }

  const origin = new URL(value)
  if (origin.protocol !== 'https:' && process.env.VERCEL_ENV === 'production') {
    throw new Error('BACKEND_ORIGIN must use HTTPS in production.')
  }
  return origin.origin
}

function forwardedHeaders(headers) {
  const result = new Headers()
  for (const [name, value] of Object.entries(headers)) {
    if (!HOP_BY_HOP_HEADERS.has(name.toLowerCase()) && value !== undefined) {
      result.set(name, Array.isArray(value) ? value.join(', ') : value)
    }
  }
  return result
}

export default async function proxyApi(req, res) {
  try {
    const origin = backendOrigin()
    // Parse against a harmless origin first so an absolute-form incoming URL
    // cannot turn this fixed proxy into an open proxy.
    const incomingUrl = new URL(req.url, 'https://vercel-proxy.invalid')
    const target = new URL(`${incomingUrl.pathname}${incomingUrl.search}`, origin)
    const method = req.method || 'GET'
    const mayHaveBody = !['GET', 'HEAD'].includes(method)
    const upstream = await fetch(target, {
      method,
      headers: forwardedHeaders(req.headers),
      body: mayHaveBody ? req : undefined,
      duplex: mayHaveBody ? 'half' : undefined,
      redirect: 'manual',
      signal: AbortSignal.timeout(70_000),
    })

    res.statusCode = upstream.status
    for (const [name, value] of upstream.headers) {
      if (!HOP_BY_HOP_HEADERS.has(name.toLowerCase()) && name.toLowerCase() !== 'set-cookie') {
        res.setHeader(name, value)
      }
    }
    const cookies = upstream.headers.getSetCookie?.()
      || (upstream.headers.get('set-cookie') ? [upstream.headers.get('set-cookie')] : [])
    if (cookies.length) {
      res.setHeader('set-cookie', cookies)
    }

    if (method === 'HEAD' || upstream.status === 204 || upstream.status === 304) {
      res.end()
      return
    }
    res.end(Buffer.from(await upstream.arrayBuffer()))
  } catch (error) {
    console.error('API proxy request failed', { message: error instanceof Error ? error.message : 'Unknown error' })
    res.statusCode = 503
    res.setHeader('content-type', 'application/json')
    res.end(JSON.stringify({ error: { code: 'API_PROXY_UNAVAILABLE', message: 'The API is temporarily unavailable.' } }))
  }
}
