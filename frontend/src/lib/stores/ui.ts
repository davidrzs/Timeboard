import { writable, get } from 'svelte/store';
import type { GroupBy } from '../types';

export const groupBy = writable<GroupBy>('project');
export const showBoard = writable(true);
export const showCalendar = writable(false);
export const filterProjectId = writable<number | null>(null);
export const quickAddOpen = writable(false);
export const planModalOpen = writable(false);
export const settingsModalOpen = writable(false);
export const isDraggingTask = writable(false);
export const burnedTaskIds = writable<Set<number>>(new Set());
export const draggedTaskId = writable<number | null>(null);
export const isOverFireZone = writable(false);

// Helper to mark task for burning when dropped in fire zone
export function checkFireZoneDrop(): number | null {
	if (get(isOverFireZone) && get(draggedTaskId)) {
		const taskId = get(draggedTaskId);
		burnedTaskIds.update((ids) => new Set([...ids, taskId!]));
		return taskId;
	}
	return null;
}
