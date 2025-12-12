<script lang="ts">
	import type { Task } from '../types';
	import { tasks } from '../stores/tasks';
	import { activeProjects } from '../stores/projects';
	import { parseQuick } from '../parser';

	interface Props {
		taskId: number | null;
		onClose: () => void;
	}

	let { taskId, onClose }: Props = $props();

	// Reactively get the task from the store
	let allTasks = $state<Task[]>([]);
	$effect(() => {
		return tasks.subscribe((t) => {
			allTasks = t;
		});
	});
	const task = $derived(taskId ? allTasks.find((t) => t.id === taskId) ?? null : null);

	let title = $state('');
	let description = $state('');
	let projectId = $state<number | null>(null);
	let dueDate = $state<string | null>(null);
	let estimatedMinutes = $state<number | null>(null);
	let priority = $state<number | null>(null);
	let newSubtaskTitle = $state('');
	let editingSubtaskId = $state<number | null>(null);
	let editingSubtaskTitle = $state('');
	let initializedForTaskId = $state<number | null>(null);
	let saveTimeout: ReturnType<typeof setTimeout> | null = null;

	// Only initialize form fields when opening a different task
	$effect(() => {
		if (task && task.id !== initializedForTaskId) {
			title = task.title;
			description = task.description;
			projectId = task.project?.id ?? null;
			dueDate = task.due_date;
			estimatedMinutes = task.estimated_minutes;
			priority = task.priority;
			initializedForTaskId = task.id;
		}
		if (!taskId) {
			initializedForTaskId = null;
		}
	});

	async function saveChanges() {
		if (!task || !title.trim()) return;
		await tasks.update(task.id, {
			title,
			description,
			project_id: projectId,
			due_date: dueDate,
			estimated_minutes: estimatedMinutes,
			priority
		});
	}

	function debouncedSave() {
		if (saveTimeout) clearTimeout(saveTimeout);
		saveTimeout = setTimeout(() => {
			saveChanges();
		}, 500);
	}

	// Autosave on field changes (after initialization)
	$effect(() => {
		if (!initializedForTaskId) return;
		// Access all form fields to track them
		const _ = [title, description, projectId, dueDate, estimatedMinutes, priority];
		debouncedSave();
	});

	function handleClose() {
		if (saveTimeout) clearTimeout(saveTimeout);
		saveChanges();
		onClose();
	}

	async function handleDelete() {
		if (!task) return;
		if (confirm('Delete this task?')) {
			if (saveTimeout) clearTimeout(saveTimeout);
			await tasks.delete(task.id);
			onClose();
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') handleClose();
	}

	async function handleAddSubtask() {
		if (!task || !newSubtaskTitle.trim()) return;
		await tasks.addSubtask(task.id, newSubtaskTitle.trim());
		newSubtaskTitle = '';
	}

	async function handleToggleSubtask(subtaskId: number) {
		if (!task) return;
		await tasks.toggleSubtask(task.id, subtaskId);
	}

	async function handleDeleteSubtask(subtaskId: number) {
		if (!task) return;
		await tasks.deleteSubtask(task.id, subtaskId);
	}

	function startEditingSubtask(subtaskId: number, currentTitle: string) {
		editingSubtaskId = subtaskId;
		editingSubtaskTitle = currentTitle;
	}

	async function saveSubtaskEdit() {
		if (!task || editingSubtaskId === null || !editingSubtaskTitle.trim()) {
			editingSubtaskId = null;
			return;
		}
		await tasks.updateSubtask(task.id, editingSubtaskId, { title: editingSubtaskTitle.trim() });
		editingSubtaskId = null;
	}

	function handleSubtaskKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') {
			e.preventDefault();
			saveSubtaskEdit();
		} else if (e.key === 'Escape') {
			editingSubtaskId = null;
		}
	}

	function handleNewSubtaskKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') {
			e.preventDefault();
			handleAddSubtask();
		}
	}

	function handleTitleInput() {
		const parsed = parseQuick(title, $activeProjects);

		// Update fields if patterns were found
		if (parsed.rawMatches.priority) {
			priority = parsed.priority;
			title = parsed.title;
		}
		if (parsed.rawMatches.project) {
			projectId = parsed.project?.id ?? null;
			title = parsed.title;
		}
		if (parsed.rawMatches.duration) {
			estimatedMinutes = parsed.duration;
			title = parsed.title;
		}
		if (parsed.rawMatches.date) {
			dueDate = parsed.dueDate?.toISOString().split('T')[0] ?? null;
			title = parsed.title;
		}
	}
</script>

{#if task}
	<div
		class="fixed inset-0 bg-black/50 flex items-start justify-center pt-[15vh] z-50"
		onclick={handleClose}
		onkeydown={handleKeydown}
		role="dialog"
		tabindex="-1"
	>
		<div
			class="bg-white rounded-xl shadow-2xl w-full max-w-lg"
			onclick={(e) => e.stopPropagation()}
			role="document"
		>
			<div class="p-4 border-b border-gray-100">
				<input
					type="text"
					bind:value={title}
					oninput={handleTitleInput}
					placeholder="Task title"
					class="w-full text-lg font-medium border-0 outline-none"
				/>
			</div>

			<div class="p-4 space-y-4">
				<div>
					<label for="task-description" class="block text-sm text-gray-500 mb-1">Description</label>
					<textarea
						id="task-description"
						bind:value={description}
						placeholder="Add details..."
						rows="3"
						class="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 resize-none"
					></textarea>
				</div>

				<div class="grid grid-cols-2 gap-4">
					<div>
						<label for="task-list" class="block text-sm text-gray-500 mb-1">List</label>
						<select
							id="task-list"
							bind:value={projectId}
							class="w-full text-sm border border-gray-200 rounded-lg px-3 py-2"
						>
							<option value={null}>None</option>
							{#each $activeProjects as project}
								<option value={project.id}>{project.name}</option>
							{/each}
						</select>
					</div>

					<div>
						<label for="task-priority" class="block text-sm text-gray-500 mb-1">Priority</label>
						<select
							id="task-priority"
							bind:value={priority}
							class="w-full text-sm border border-gray-200 rounded-lg px-3 py-2"
						>
							<option value={null}>None</option>
							<option value={1}>High</option>
							<option value={2}>Medium</option>
							<option value={3}>Low</option>
						</select>
					</div>

					<div>
						<label for="task-due" class="block text-sm text-gray-500 mb-1">Due</label>
						<input
							id="task-due"
							type="date"
							bind:value={dueDate}
							class="w-full text-sm border border-gray-200 rounded-lg px-3 py-2"
						/>
					</div>

					<div>
						<label for="task-estimate" class="block text-sm text-gray-500 mb-1">Estimate</label>
						<input
							id="task-estimate"
							type="number"
							bind:value={estimatedMinutes}
							placeholder="min"
							class="w-full text-sm border border-gray-200 rounded-lg px-3 py-2"
						/>
					</div>
				</div>

				<div>
					<span class="block text-sm text-gray-500 mb-2">Subtasks</span>
					<div class="space-y-1">
						{#each task.subtasks as subtask (subtask.id)}
							<div class="flex items-center gap-2 group">
								<input
									type="checkbox"
									checked={subtask.completed}
									onchange={() => handleToggleSubtask(subtask.id)}
									class="w-4 h-4 rounded border-gray-300 flex-shrink-0"
								/>
								{#if editingSubtaskId === subtask.id}
									<input
										type="text"
										bind:value={editingSubtaskTitle}
										onblur={saveSubtaskEdit}
										onkeydown={handleSubtaskKeydown}
										class="flex-1 text-sm bg-transparent outline-none"
									/>
								{:else}
									<span
										class="flex-1 text-sm cursor-pointer {subtask.completed ? 'line-through text-gray-400' : ''}"
										ondblclick={() => startEditingSubtask(subtask.id, subtask.title)}
										onkeydown={(e) => { if (e.key === 'Enter') startEditingSubtask(subtask.id, subtask.title); }}
										role="button"
										tabindex="0"
									>
										{subtask.title}
									</span>
								{/if}
								<button
									onclick={() => handleDeleteSubtask(subtask.id)}
									class="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500 text-sm px-1"
									aria-label="Delete subtask"
								>
									&times;
								</button>
							</div>
						{/each}
						<div class="flex items-center gap-2">
							<div class="w-4 h-4 rounded border border-gray-300 flex-shrink-0 opacity-50"></div>
							<input
								type="text"
								bind:value={newSubtaskTitle}
								onkeydown={handleNewSubtaskKeydown}
								onblur={handleAddSubtask}
								placeholder="Add subtask..."
								class="flex-1 text-sm bg-transparent outline-none text-gray-500 placeholder:text-gray-400"
							/>
						</div>
					</div>
				</div>
			</div>

			<div class="p-4 border-t border-gray-100">
				<button
					onclick={handleDelete}
					class="px-4 py-2 text-sm text-red-600 hover:bg-red-50 rounded-lg"
				>
					Delete
				</button>
			</div>
		</div>
	</div>
{/if}
