import { createClient, type SupabaseClient } from '@supabase/supabase-js'

let client: SupabaseClient | null = null

export function getSupabaseClient(): SupabaseClient {
  if (client) return client

  const url = import.meta.env.VITE_SUPABASE_URL as string | undefined
  const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined

  if (!url || !anonKey) {
    throw new Error('Supabase 未配置：缺少 VITE_SUPABASE_URL 或 VITE_SUPABASE_ANON_KEY')
  }

  client = createClient(url, anonKey)
  return client
}

