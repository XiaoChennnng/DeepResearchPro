import { create } from 'zustand'
import type { Session, User } from '@supabase/supabase-js'
import { getSupabaseClient } from '@/services/supabase'

interface AuthState {
  initialized: boolean
  isLoading: boolean
  session: Session | null
  user: User | null
  error: string | null
  init: () => Promise<void>
  signInWithPassword: (params: { email: string; password: string }) => Promise<void>
  signUpWithPassword: (params: { email: string; password: string }) => Promise<void>
  signOut: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set, get) => {
  return {
    initialized: false,
    isLoading: false,
    session: null,
    user: null,
    error: null,

    init: async () => {
      if (get().initialized) return
      set({ initialized: true, isLoading: true, error: null })

      try {
        const supabase = getSupabaseClient()
        const { data, error } = await supabase.auth.getSession()

        if (error) throw error

        set({ session: data.session, user: data.session?.user ?? null })

        supabase.auth.onAuthStateChange((_event, session) => {
          set({ session, user: session?.user ?? null })
        })
      } catch (e) {
        const message = e instanceof Error ? e.message : '认证初始化失败'
        set({ error: message })
      } finally {
        set({ isLoading: false })
      }
    },

    signInWithPassword: async ({ email, password }) => {
      set({ isLoading: true, error: null })
      try {
        const supabase = getSupabaseClient()
        const { error } = await supabase.auth.signInWithPassword({ email, password })
        if (error) throw error
      } catch (e) {
        const message = e instanceof Error ? e.message : '登录失败'
        set({ error: message })
        throw e
      } finally {
        set({ isLoading: false })
      }
    },

    signUpWithPassword: async ({ email, password }) => {
      set({ isLoading: true, error: null })
      try {
        const supabase = getSupabaseClient()
        const { error } = await supabase.auth.signUp({ email, password })
        if (error) throw error
      } catch (e) {
        const message = e instanceof Error ? e.message : '注册失败'
        set({ error: message })
        throw e
      } finally {
        set({ isLoading: false })
      }
    },

    signOut: async () => {
      set({ isLoading: true, error: null })
      try {
        const supabase = getSupabaseClient()
        const { error } = await supabase.auth.signOut()
        if (error) throw error

        set({ session: null, user: null })
      } catch (e) {
        const message = e instanceof Error ? e.message : '退出失败'
        set({ error: message })
        throw e
      } finally {
        set({ isLoading: false })
      }
    },
  }
})
