import type { Project, Subtask, Task, User, UserSettings, AuthStatus, GoogleCalendar, CalendarEvent, CalendarSyncState, SyncResult, ProposedPlan } from './types';

const API_URL = import.meta.env.PUBLIC_API_URL || 'http://localhost:8000/api';

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
	const response = await fetch(`${API_URL}${path}`, {
		...options,
		credentials: 'include',
		headers: {
			'Content-Type': 'application/json',
			...options.headers
		}
	});

	if (!response.ok) {
		throw new Error(`API error: ${response.status}`);
	}

	return response.json();
}

export const api = {
	auth: {
		me: () => request<User>('/auth/me'),
		status: () => request<AuthStatus>('/auth/status'),
		googleLoginUrl: () => request<{ url: string }>('/auth/google-login-url'),
		logout: () => request<{ ok: boolean }>('/auth/logout', { method: 'POST' })
	},

	projects: {
		list: () => request<Project[]>('/projects/'),
		create: (data: { name: string; color: string }) =>
			request<Project>('/projects/', { method: 'POST', body: JSON.stringify(data) }),
		update: (id: number, data: Partial<Project>) =>
			request<Project>(`/projects/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
		delete: (id: number) =>
			request<{ ok: boolean }>(`/projects/${id}`, { method: 'DELETE' }),
		reorder: (order: number[]) =>
			request<{ ok: boolean }>('/projects/reorder', { method: 'PATCH', body: JSON.stringify({ order }) })
	},

	tasks: {
		list: (params?: { project_id?: number; time_horizon?: string; completed?: boolean }) => {
			const searchParams = new URLSearchParams();
			if (params?.project_id) searchParams.set('project_id', String(params.project_id));
			if (params?.time_horizon) searchParams.set('time_horizon', params.time_horizon);
			if (params?.completed !== undefined) searchParams.set('completed', String(params.completed));
			const query = searchParams.toString();
			return request<Task[]>(`/tasks/${query ? `?${query}` : ''}`);
		},
		create: (data: {
			title: string;
			project_id?: number | null;
			time_horizon?: string;
			due_date?: string | null;
			estimated_minutes?: number | null;
			priority?: number | null;
			description?: string;
		}) => request<Task>('/tasks/', { method: 'POST', body: JSON.stringify(data) }),
		update: (id: number, data: {
			title?: string;
			description?: string;
			project_id?: number | null;
			time_horizon?: string;
			due_date?: string | null;
			estimated_minutes?: number | null;
			priority?: number | null;
			scheduled_start?: string | null;
			scheduled_end?: string | null;
		}) => request<Task>(`/tasks/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
		delete: (id: number) =>
			request<{ ok: boolean }>(`/tasks/${id}`, { method: 'DELETE' }),
		move: (id: number, data: { time_horizon: string; position: number; project_id?: number }) =>
			request<{ ok: boolean }>(`/tasks/${id}/move`, { method: 'PATCH', body: JSON.stringify(data) }),
		complete: (id: number) =>
			request<Task>(`/tasks/${id}/complete`, { method: 'POST' }),
		uncomplete: (id: number) =>
			request<Task>(`/tasks/${id}/uncomplete`, { method: 'POST' }),
		createSubtask: (taskId: number, title: string) =>
			request<Subtask>(`/tasks/${taskId}/subtasks`, { method: 'POST', body: JSON.stringify({ title }) }),
		reorderSubtasks: (taskId: number, order: number[]) =>
			request<{ ok: boolean }>(`/tasks/${taskId}/subtasks/reorder`, { method: 'PATCH', body: JSON.stringify({ order }) })
	},

	subtasks: {
		update: (id: number, data: { title?: string; completed?: boolean; position?: number }) =>
			request<Subtask>(`/subtasks/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
		delete: (id: number) =>
			request<{ ok: boolean }>(`/subtasks/${id}`, { method: 'DELETE' }),
		toggle: (id: number) =>
			request<Subtask>(`/subtasks/${id}/toggle`, { method: 'POST' })
	},

	settings: {
		get: () => request<UserSettings>('/settings/'),
		update: (data: Partial<UserSettings>) =>
			request<UserSettings>('/settings/', { method: 'PATCH', body: JSON.stringify(data) })
	},

	calendar: {
		listCalendars: () => request<GoogleCalendar[]>('/calendar/calendars'),
		listEvents: (start: string, end: string) =>
			request<CalendarEvent[]>(`/calendar/events?start=${start}&end=${end}`),
		listCachedEvents: (start: string, end: string) =>
			request<CalendarEvent[]>(`/calendar/events/cached?start=${start}&end=${end}`),
		listSyncStates: () => request<CalendarSyncState[]>('/calendar/sync-states'),
		sync: () => request<SyncResult[]>('/calendar/sync', { method: 'POST' })
	},

	llm: {
		generateSchedule: () => request<ProposedPlan>('/llm/generate-schedule', { method: 'POST' }),
		commitSchedule: (slots: { task_id: number; start_time: string; end_time: string }[]) =>
			request<{ ok: boolean }>('/llm/commit-schedule', { method: 'POST', body: JSON.stringify({ slots }) })
	}
};
