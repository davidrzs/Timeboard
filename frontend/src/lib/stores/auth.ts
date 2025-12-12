import { writable, derived } from 'svelte/store';
import type { User } from '../types';
import { api } from '../api';

const API_URL = import.meta.env.PUBLIC_API_URL || '/api';
const BASE_URL = API_URL.replace(/\/api$/, '') || '';

interface AuthState {
	user: User | null;
	googleConnected: boolean;
}

function createAuthStore() {
	const { subscribe, set, update } = writable<AuthState>({
		user: null,
		googleConnected: false
	});

	return {
		subscribe,
		async check() {
			try {
				const status = await api.auth.status();
				set({
					user: status.user,
					googleConnected: status.google_connected
				});
				return status.user;
			} catch {
				set({ user: null, googleConnected: false });
				return null;
			}
		},
		async googleLogin() {
			// Redirect to Google OAuth
			const { url } = await api.auth.googleLoginUrl();
			window.location.href = `${BASE_URL}${url}`;
		},
		async logout() {
			await api.auth.logout();
			set({ user: null, googleConnected: false });
		},
		set
	};
}

export const auth = createAuthStore();

// Derived store for just the user (backwards compatibility)
export const user = derived(auth, ($auth) => $auth.user);
export const googleConnected = derived(auth, ($auth) => $auth.googleConnected);
