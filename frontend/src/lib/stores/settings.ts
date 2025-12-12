import { writable, derived } from 'svelte/store';
import type { UserSettings } from '../types';
import { api } from '../api';

const DEFAULT_SETTINGS: UserSettings = {
	scheduling_preferences: '',
	morning_email_time: '06:00',
	morning_email_enabled: true,
	has_seen_tour: false,
	week_starts_on: 1,
	scheduling_windows: {}
};

function createSettingsStore() {
	const { subscribe, set, update } = writable<UserSettings>(DEFAULT_SETTINGS);

	return {
		subscribe,
		async load() {
			try {
				const settings = await api.settings.get();
				set(settings);
				return settings;
			} catch {
				set(DEFAULT_SETTINGS);
				return DEFAULT_SETTINGS;
			}
		},
		async update(data: Partial<UserSettings>) {
			const updated = await api.settings.update(data);
			set(updated);
			return updated;
		},
		reset() {
			set(DEFAULT_SETTINGS);
		}
	};
}

export const settings = createSettingsStore();

export const weekStartsOn = derived(settings, ($settings) => $settings.week_starts_on);
