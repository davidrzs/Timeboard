import { writable, derived, get } from 'svelte/store';
import type { Task, TimeHorizon, Project, Subtask } from '../types';
import { api } from '../api';
import { projects } from './projects';

function createTasksStore() {
	const { subscribe, set, update } = writable<Task[]>([]);

	return {
		subscribe,
		async load() {
			const tasks = await api.tasks.list();
			set(tasks);
			return tasks;
		},
		async create(data: {
			title: string;
			project_id?: number | null;
			time_horizon?: string;
			due_date?: string | null;
			estimated_minutes?: number | null;
			priority?: number | null;
			description?: string;
		}) {
			const task = await api.tasks.create(data);
			update((tasks) => [...tasks, task]);
			return task;
		},
		async update(id: number, data: {
			title?: string;
			description?: string;
			project_id?: number | null;
			time_horizon?: string;
			due_date?: string | null;
			estimated_minutes?: number | null;
			priority?: number | null;
			scheduled_start?: string | null;
			scheduled_end?: string | null;
		}) {
			const task = await api.tasks.update(id, data);
			update((tasks) => tasks.map((t) => (t.id === id ? task : t)));
			return task;
		},
		async delete(id: number) {
			await api.tasks.delete(id);
			update((tasks) => tasks.filter((t) => t.id !== id));
		},
		async move(id: number, time_horizon: string, position: number, project_id?: number) {
			await api.tasks.move(id, { time_horizon, position, project_id });
			// Refetch tasks to get accurate time_horizon computed from due_date
			await this.load();
		},
		async complete(id: number) {
			const task = await api.tasks.complete(id);
			update((tasks) => tasks.map((t) => (t.id === id ? task : t)));
			return task;
		},
		async uncomplete(id: number) {
			const task = await api.tasks.uncomplete(id);
			update((tasks) => tasks.map((t) => (t.id === id ? task : t)));
			return task;
		},
		updateLocal(id: number, data: Partial<Task>) {
			update((tasks) => tasks.map((t) => (t.id === id ? { ...t, ...data } : t)));
		},
		async addSubtask(taskId: number, title: string) {
			const subtask = await api.tasks.createSubtask(taskId, title);
			update((tasks) =>
				tasks.map((t) =>
					t.id === taskId ? { ...t, subtasks: [...t.subtasks, subtask] } : t
				)
			);
			return subtask;
		},
		async updateSubtask(taskId: number, subtaskId: number, data: { title?: string; completed?: boolean }) {
			const subtask = await api.subtasks.update(subtaskId, data);
			update((tasks) =>
				tasks.map((t) =>
					t.id === taskId
						? { ...t, subtasks: t.subtasks.map((s) => (s.id === subtaskId ? subtask : s)) }
						: t
				)
			);
			return subtask;
		},
		async deleteSubtask(taskId: number, subtaskId: number) {
			await api.subtasks.delete(subtaskId);
			update((tasks) =>
				tasks.map((t) =>
					t.id === taskId
						? { ...t, subtasks: t.subtasks.filter((s) => s.id !== subtaskId) }
						: t
				)
			);
		},
		async toggleSubtask(taskId: number, subtaskId: number) {
			const subtask = await api.subtasks.toggle(subtaskId);
			update((tasks) =>
				tasks.map((t) =>
					t.id === taskId
						? { ...t, subtasks: t.subtasks.map((s) => (s.id === subtaskId ? subtask : s)) }
						: t
				)
			);
			return subtask;
		},
		async reorderSubtasks(taskId: number, order: number[]) {
			await api.tasks.reorderSubtasks(taskId, order);
			update((tasks) =>
				tasks.map((t) => {
					if (t.id !== taskId) return t;
					const reordered = order.map((id, idx) => {
						const subtask = t.subtasks.find((s) => s.id === id);
						return subtask ? { ...subtask, position: idx } : null;
					}).filter((s): s is Subtask => s !== null);
					return { ...t, subtasks: reordered };
				})
			);
		}
	};
}

export const tasks = createTasksStore();

export const tasksByHorizon = derived(tasks, ($tasks) => {
	const grouped: Record<TimeHorizon, Task[]> = {
		today: [],
		this_week: [],
		next_week: [],
		later: [],
		backlog: []
	};

	for (const task of $tasks) {
		const horizon = task.time_horizon && grouped[task.time_horizon] ? task.time_horizon : 'backlog';
		grouped[horizon].push(task);
	}

	// Sort: incomplete first (by position), then completed (by completed_at desc)
	for (const horizon of Object.keys(grouped) as TimeHorizon[]) {
		grouped[horizon].sort((a, b) => {
			if (a.completed !== b.completed) return a.completed ? 1 : -1;
			if (a.completed && b.completed) {
				return (b.completed_at || '').localeCompare(a.completed_at || '');
			}
			return a.position - b.position;
		});
	}

	return grouped;
});

export const tasksByProject = derived(tasks, ($tasks) => {
	const grouped: Record<number | 'none', Task[]> = { none: [] };

	for (const task of $tasks) {
		const key = task.project?.id ?? 'none';
		if (!grouped[key]) grouped[key] = [];
		grouped[key].push(task);
	}

	// Sort: incomplete first (by position), then completed (by completed_at desc)
	for (const key of Object.keys(grouped)) {
		grouped[key as keyof typeof grouped].sort((a, b) => {
			if (a.completed !== b.completed) return a.completed ? 1 : -1;
			if (a.completed && b.completed) {
				return (b.completed_at || '').localeCompare(a.completed_at || '');
			}
			return a.position - b.position;
		});
	}

	return grouped;
});
