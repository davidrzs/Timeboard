export interface User {
	id: number;
	email: string;
	first_name: string;
	last_name: string;
}

export interface Project {
	id: number;
	name: string;
	color: string;
	position: number;
	archived: boolean;
	created_at: string;
	updated_at: string;
}

export interface Subtask {
	id: number;
	title: string;
	completed: boolean;
	position: number;
}

export interface Task {
	id: number;
	title: string;
	description: string;
	project: Project | null;
	time_horizon: TimeHorizon;
	position: number;
	due_date: string | null;
	estimated_minutes: number | null;
	priority: number | null;
	scheduled_start: string | null;
	scheduled_end: string | null;
	completed: boolean;
	completed_at: string | null;
	reschedule_count: number;
	created_at: string;
	updated_at: string;
	subtasks: Subtask[];
}

export type TimeHorizon = 'today' | 'this_week' | 'next_week' | 'later' | 'backlog';

export const TIME_HORIZONS: { value: TimeHorizon; label: string }[] = [
	{ value: 'today', label: 'Today' },
	{ value: 'this_week', label: 'This Week' },
	{ value: 'next_week', label: 'Next Week' },
	{ value: 'later', label: 'Later' },
	{ value: 'backlog', label: 'Backlog' }
];

export interface SchedulingWindow {
	start: string;
	end: string;
}

export type SchedulingWindows = Record<string, SchedulingWindow[]>;

export interface UserSettings {
	scheduling_preferences: string;
	morning_email_time: string;
	morning_email_enabled: boolean;
	has_seen_tour: boolean;
	week_starts_on: number;
	scheduling_windows: SchedulingWindows;
}

export interface AuthStatus {
	authenticated: boolean;
	user: User | null;
	google_connected: boolean;
}

export interface GoogleCalendar {
	id: string;
	name: string;
	color: string;
	primary: boolean;
}

export interface CalendarEvent {
	id: number;
	gcal_id: string;
	calendar_id: string;
	title: string;
	start: string;
	end: string;
	all_day: boolean;
	location?: string;
	description?: string;
}

export interface CalendarSyncState {
	id: number;
	calendar_id: string;
	calendar_name: string;
	calendar_color: string;
	is_enabled: boolean;
	last_synced_at: string | null;
	has_sync_token: boolean;
}

export interface SyncResult {
	calendar_id: string;
	created: number;
	updated: number;
	deleted: number;
	errors: string[];
	full_sync_performed: boolean;
}

export type GroupBy = 'time' | 'project';

export const PROJECT_COLORS = [
	'#3B82F6',
	'#22C55E',
	'#EAB308',
	'#A855F7',
	'#EC4899',
	'#F97316',
	'#14B8A6',
	'#EF4444'
];

export interface TimeSlot {
	task_id: number;
	start_time: string;
	estimated_minutes: number;
}

export interface ProposedPlan {
	message: string;
	schedule: TimeSlot[];
}
