import { createClient } from "@supabase/supabase-js";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    // Don't auto-create a session from the tokens in the email-confirmation
    // link's URL. This forces the user to land on the sign-in page and log
    // in manually after confirming their email, instead of being silently
    // signed in.
    detectSessionInUrl: false,
  },
});