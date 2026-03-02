async function fetchHealth(url: string) {
  const res = await fetch(url, { cache: "no-store" })
  return res.text()
}

export default async function HealthPage() {
  const ingestion = await fetchHealth(process.env.NEXT_PUBLIC_INGESTION_URL + "/health")
  const inference = await fetchHealth(process.env.NEXT_PUBLIC_INFERENCE_URL + "/health")
  const identity = await fetchHealth(process.env.NEXT_PUBLIC_IDENTITY_URL + "/health")
  const sync = await fetchHealth(process.env.NEXT_PUBLIC_SYNC_URL + "/health")
  return (
    <main>
      <h1>Device Health</h1>
      <ul>
        <li>Ingestion: {ingestion}</li>
        <li>Inference: {inference}</li>
        <li>Identity: {identity}</li>
        <li>Sync: {sync}</li>
      </ul>
    </main>
  )
}
