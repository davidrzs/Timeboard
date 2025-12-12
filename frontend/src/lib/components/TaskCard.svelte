<script lang="ts">
	import type { Task } from '../types';
	import { tasks } from '../stores/tasks';

	interface Props {
		task: Task;
		onEdit?: (task: Task) => void;
	}

	let { task, onEdit }: Props = $props();

	function formatDueDate(dateStr: string | null): string {
		if (!dateStr) return '';
		const date = new Date(dateStr);
		const today = new Date();
		const tomorrow = new Date(today);
		tomorrow.setDate(tomorrow.getDate() + 1);

		if (date.toDateString() === today.toDateString()) return 'Today';
		if (date.toDateString() === tomorrow.toDateString()) return 'Tomorrow';

		return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
	}

	function formatEstimate(minutes: number | null): string {
		if (!minutes) return '';
		if (minutes < 60) return `${minutes}m`;
		const hours = Math.floor(minutes / 60);
		const mins = minutes % 60;
		return mins ? `${hours}h${mins}m` : `${hours}h`;
	}

	async function toggleComplete(e: MouseEvent) {
		e.stopPropagation();
		if (task.completed) {
			await tasks.uncomplete(task.id);
		} else {
			await tasks.complete(task.id);
		}
	}

	function getSubtaskProgress(): { completed: number; total: number } | null {
		if (!task.subtasks || task.subtasks.length === 0) return null;
		const completed = task.subtasks.filter((s) => s.completed).length;
		return { completed, total: task.subtasks.length };
	}

	function getPriorityColor(priority: number | null): string {
		if (priority === 1) return 'text-red-500';
		if (priority === 2) return 'text-orange-500';
		if (priority === 3) return 'text-blue-500';
		return '';
	}

	const subtaskProgress = $derived(getSubtaskProgress());
</script>

<div
	class="group bg-white rounded shadow-sm hover:shadow transition-shadow cursor-pointer"
	class:opacity-50={task.completed}
	onclick={() => onEdit?.(task)}
	role="button"
	tabindex="0"
	onkeydown={(e) => e.key === 'Enter' && onEdit?.(task)}
>
	{#if task.project}
		<div
			class="h-1 rounded-t"
			style="background-color: {task.project.color}"
		></div>
	{/if}

	<div class="p-2">
		<div class="flex items-start gap-2">
			<button
				onclick={toggleComplete}
				class="mt-0.5 w-4 h-4 rounded border flex-shrink-0 flex items-center justify-center transition-colors"
				class:border-gray-300={!task.completed}
				class:hover:border-gray-400={!task.completed}
				class:bg-green-500={task.completed}
				class:border-green-500={task.completed}
			>
				{#if task.completed}
					<svg class="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" />
					</svg>
				{/if}
			</button>

			{#if task.priority}
				<svg class="w-3 h-3 flex-shrink-0 mt-0.5 {getPriorityColor(task.priority)}" fill="currentColor" viewBox="0 0 20 20">
					<path fill-rule="evenodd" d="M3 6a3 3 0 013-3h10a1 1 0 01.8 1.6L14.25 8l2.55 3.4A1 1 0 0116 13H6a1 1 0 00-1 1v3a1 1 0 11-2 0V6z" clip-rule="evenodd" />
				</svg>
			{/if}

			<span
				class="text-sm text-gray-800 leading-snug"
				class:line-through={task.completed}
				class:text-gray-500={task.completed}
			>
				{task.title}
			</span>
		</div>

		{#if task.due_date || task.estimated_minutes || task.project || subtaskProgress}
			<div class="flex items-center gap-2 mt-1.5 ml-6 text-xs text-gray-400">
				{#if task.project}
					<span class="truncate max-w-[100px]">{task.project.name}</span>
				{/if}
				{#if subtaskProgress}
					<div class="flex items-center gap-1.5">
						<div class="w-12 h-1 bg-gray-200 rounded-full overflow-hidden">
							<div
								class="h-full rounded-full transition-all"
								style="width: {(subtaskProgress.completed / subtaskProgress.total) * 100}%; background-color: {subtaskProgress.completed === subtaskProgress.total ? '#22c55e' : (task.project?.color ?? '#9ca3af')}"
							></div>
						</div>
						<span class="text-[10px]">{subtaskProgress.completed}/{subtaskProgress.total}</span>
					</div>
				{/if}
				{#if task.due_date}
					<span class="flex items-center gap-0.5">
						<svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
						</svg>
						{formatDueDate(task.due_date)}
					</span>
				{/if}
				{#if task.estimated_minutes}
					<span class="flex items-center gap-0.5">
						<svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
						</svg>
						{formatEstimate(task.estimated_minutes)}
					</span>
				{/if}
			</div>
		{/if}
	</div>
</div>
