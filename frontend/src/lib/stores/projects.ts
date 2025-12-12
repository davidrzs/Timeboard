import { writable, derived } from 'svelte/store';
import type { Project } from '../types';
import { api } from '../api';

function createProjectsStore() {
	const { subscribe, set, update } = writable<Project[]>([]);

	return {
		subscribe,
		async load() {
			const projects = await api.projects.list();
			set(projects);
			return projects;
		},
		async create(data: { name: string; color: string }) {
			const project = await api.projects.create(data);
			update((projects) => [...projects, project]);
			return project;
		},
		async update(id: number, data: Partial<Project>) {
			const project = await api.projects.update(id, data);
			update((projects) => projects.map((p) => (p.id === id ? project : p)));
			return project;
		},
		async delete(id: number) {
			await api.projects.delete(id);
			update((projects) => projects.filter((p) => p.id !== id));
		},
		async reorder(order: number[]) {
			await api.projects.reorder(order);
			update((projects) => {
				const sorted = [...projects];
				sorted.sort((a, b) => order.indexOf(a.id) - order.indexOf(b.id));
				return sorted.map((p, i) => ({ ...p, position: i }));
			});
		}
	};
}

export const projects = createProjectsStore();

export const activeProjects = derived(projects, ($projects) =>
	$projects.filter((p) => !p.archived)
);
