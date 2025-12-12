<script lang="ts">
	import { dndzone } from 'svelte-dnd-action';
	import type { Task, TimeHorizon, Project } from '../types';
	import { PROJECT_COLORS } from '../types';
	import TaskCard from './TaskCard.svelte';
	import { tasks } from '../stores/tasks';
	import { projects, activeProjects } from '../stores/projects';
	import { isDraggingTask, burnedTaskIds, draggedTaskId, checkFireZoneDrop, isOverFireZone } from '../stores/ui';
	import { parseQuick, formatDuration, formatDate, type QuickParsed } from '../parser';
	import { get } from 'svelte/store';

	interface Props {
		title: string;
		columnId: string;
		items: Task[];
		color?: string;
		type?: 'project' | 'time';
		project?: Project;
		onEditTask?: (task: Task) => void;
	}

	let { title, columnId, items, color, type = 'time', project, onEditTask }: Props = $props();

	// Inline editing state
	let isEditingName = $state(false);
	let editedName = $state('');
	let nameInputRef = $state<HTMLInputElement | null>(null);
	let showColorPicker = $state(false);
	let colorPickerRef = $state<HTMLDivElement | null>(null);

	$effect(() => {
		if (isEditingName && nameInputRef) {
			nameInputRef.focus();
			nameInputRef.select();
		}
	});

	function startEditingName() {
		if (!project) return;
		editedName = project.name;
		isEditingName = true;
	}

	async function saveName() {
		if (!project || !editedName.trim()) {
			isEditingName = false;
			return;
		}
		if (editedName.trim() !== project.name) {
			await projects.update(project.id, { name: editedName.trim() });
		}
		isEditingName = false;
	}

	function handleNameKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') {
			e.preventDefault();
			saveName();
		} else if (e.key === 'Escape') {
			isEditingName = false;
		}
	}

	async function selectColor(newColor: string) {
		if (!project) return;
		await projects.update(project.id, { color: newColor });
		showColorPicker = false;
	}

	function handleColorPickerClickOutside(e: MouseEvent) {
		if (colorPickerRef && !colorPickerRef.contains(e.target as Node)) {
			showColorPicker = false;
		}
	}

	$effect(() => {
		if (showColorPicker) {
			document.addEventListener('click', handleColorPickerClickOutside);
			return () => document.removeEventListener('click', handleColorPickerClickOutside);
		}
	});

	let localItems = $state(items);
	let isAdding = $state(false);
	let newTaskTitle = $state('');
	let inputRef = $state<HTMLTextAreaElement | null>(null);
	let quickParsed = $state<QuickParsed | null>(null);

	$effect(() => {
		if (newTaskTitle.trim()) {
			quickParsed = parseQuick(newTaskTitle, $activeProjects);
		} else {
			quickParsed = null;
		}
	});

	$effect(() => {
		localItems = items;
	});

	$effect(() => {
		if (isAdding && inputRef) {
			inputRef.focus();
		}
	});

	function handleDndConsider(e: CustomEvent<{ items: Task[] }>) {
		localItems = e.detail.items;
		$isDraggingTask = true;

		// Track which task is being dragged (find the one that left)
		const draggedOut = items.find((t) => !e.detail.items.some((i) => i.id === t.id));
		if (draggedOut) {
			$draggedTaskId = draggedOut.id;
		}
	}

	async function handleDndFinalize(e: CustomEvent<{ items: Task[] }>) {
		// Check if dropped in delete zone
		const burnedId = checkFireZoneDrop();
		if (burnedId) {
			await tasks.delete(burnedId);
			await tasks.load();
		}

		$isDraggingTask = false;
		$draggedTaskId = null;

		// Skip processing if task was burned (deleted via fire zone)
		const burned = get(burnedTaskIds);

		// Filter out burned items from localItems
		localItems = e.detail.items.filter((item) => !burned.has(item.id));

		// Clear burned IDs after processing
		setTimeout(() => burnedTaskIds.set(new Set()), 100);

		const movedTask = e.detail.items.find((item, idx) => {
			// Skip burned tasks
			if (burned.has(item.id)) return false;

			const originalItem = items.find((t) => t.id === item.id);
			// Task came from another column (not in original items)
			if (!originalItem) return true;
			// Task reordered within this column
			if (type === 'project') {
				return originalItem.position !== idx || String(originalItem.project?.id) !== columnId;
			}
			return originalItem.position !== idx || originalItem.time_horizon !== columnId;
		});

		if (movedTask && !burned.has(movedTask.id)) {
			const newPosition = localItems.findIndex((t) => t.id === movedTask.id);
			if (type === 'project') {
				await tasks.move(movedTask.id, movedTask.time_horizon, newPosition, parseInt(columnId));
			} else {
				await tasks.move(movedTask.id, columnId, newPosition);
			}
		}
	}

	async function handleAddCard() {
		if (!newTaskTitle.trim()) {
			isAdding = false;
			return;
		}

		const parsed = quickParsed;
		const taskTitle = parsed?.title || newTaskTitle.trim();

		if (type === 'project') {
			await tasks.create({
				title: taskTitle,
				project_id: parsed?.project?.id ?? parseInt(columnId),
				time_horizon: 'backlog',
				due_date: parsed?.dueDate ? parsed.dueDate.toISOString().split('T')[0] : null,
				estimated_minutes: parsed?.duration ?? null
			});
		} else {
			await tasks.create({
				title: taskTitle,
				project_id: parsed?.project?.id ?? null,
				time_horizon: columnId as TimeHorizon,
				due_date: parsed?.dueDate ? parsed.dueDate.toISOString().split('T')[0] : null,
				estimated_minutes: parsed?.duration ?? null
			});
		}

		newTaskTitle = '';
		quickParsed = null;
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			handleAddCard();
		} else if (e.key === 'Escape') {
			isAdding = false;
			newTaskTitle = '';
		}
	}

	function handleBlur() {
		if (!newTaskTitle.trim()) {
			isAdding = false;
		}
	}
</script>

<div class="flex flex-col bg-gray-100 rounded-lg min-w-[272px] max-w-[272px] max-h-[calc(100vh-180px)] min-h-[200px]">
	<div class="flex items-center gap-2 px-2 py-2">
		{#if color}
			<div class="relative">
				<button
					type="button"
					onclick={(e) => { e.stopPropagation(); showColorPicker = !showColorPicker; }}
					class="w-2 h-2 rounded-full flex-shrink-0 hover:ring-2 hover:ring-offset-1 hover:ring-gray-400 transition-all {project ? 'cursor-pointer' : ''}"
					style="background-color: {color}"
					disabled={!project}
					aria-label="Change project color"
				></button>
				{#if showColorPicker && project}
					<div
						bind:this={colorPickerRef}
						role="dialog"
						aria-label="Color picker"
						tabindex="-1"
						class="absolute top-full left-0 mt-1 p-2 bg-white rounded-lg shadow-lg border border-gray-200 z-50"
						onclick={(e) => e.stopPropagation()}
						onkeydown={(e) => { if (e.key === 'Escape') showColorPicker = false; }}
					>
						<div class="flex gap-1.5 flex-wrap w-[140px]" role="listbox" aria-label="Available colors">
							{#each PROJECT_COLORS as c}
								<button
									type="button"
									onclick={() => selectColor(c)}
									class="w-6 h-6 rounded-full border-2 hover:scale-110 transition-transform"
									style="background-color: {c}; border-color: {color === c ? '#1f2937' : 'transparent'}"
									aria-label="Select color {c}"
									aria-selected={color === c}
									role="option"
								></button>
							{/each}
						</div>
					</div>
				{/if}
			</div>
		{/if}
		{#if isEditingName && project}
			<input
				bind:this={nameInputRef}
				bind:value={editedName}
				onkeydown={handleNameKeydown}
				onblur={saveName}
				class="font-medium text-sm text-gray-700 bg-white px-1 py-0.5 rounded border border-gray-300 outline-none flex-1 min-w-0"
			/>
		{:else}
			<button
				type="button"
				onclick={startEditingName}
				class="font-medium text-sm text-gray-700 truncate text-left {project ? 'hover:bg-gray-200 px-1 py-0.5 -mx-1 rounded cursor-pointer' : ''}"
				disabled={!project}
			>
				{title}
			</button>
		{/if}
		<span class="text-xs text-gray-400 flex-shrink-0">{localItems.length}</span>
	</div>

	<div
		class="flex-1 flex flex-col gap-1.5 px-2 pb-12 overflow-y-auto min-h-[100px]"
		use:dndzone={{ items: localItems, flipDurationMs: 150, dropTargetStyle: {} }}
		onconsider={handleDndConsider}
		onfinalize={handleDndFinalize}
	>
		{#each localItems as task (task.id)}
			<TaskCard {task} onEdit={onEditTask} />
		{/each}
	</div>

	<!-- Add card area overlaps the drop zone padding -->
	<div class="px-2 pb-2 -mt-10 relative z-10">
		{#if isAdding}
			<div class="bg-white rounded shadow-sm">
				<textarea
					bind:this={inputRef}
					bind:value={newTaskTitle}
					onkeydown={handleKeydown}
					onblur={handleBlur}
					placeholder="task by friday ~30m"
					rows="2"
					class="w-full text-sm p-2 border-0 rounded resize-none outline-none"
				></textarea>
				{#if quickParsed && (quickParsed.project || quickParsed.duration || quickParsed.dueDate)}
					<div class="flex flex-wrap gap-1 px-2 pb-1">
						{#if quickParsed.project}
							<span class="inline-flex items-center gap-1 px-1.5 py-0.5 text-xs rounded bg-blue-100 text-blue-700">
								<span class="w-1.5 h-1.5 rounded-full" style="background-color: {quickParsed.project.color}"></span>
								{quickParsed.project.name}
							</span>
						{/if}
						{#if quickParsed.dueDate}
							<span class="px-1.5 py-0.5 text-xs rounded bg-amber-100 text-amber-700">
								{formatDate(quickParsed.dueDate)}
							</span>
						{/if}
						{#if quickParsed.duration}
							<span class="px-1.5 py-0.5 text-xs rounded bg-green-100 text-green-700">
								{formatDuration(quickParsed.duration)}
							</span>
						{/if}
					</div>
				{/if}
				<div class="flex gap-1 p-1 pt-0">
					<button
						onclick={handleAddCard}
						class="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
					>
						Add
					</button>
					<button
						onclick={() => { isAdding = false; newTaskTitle = ''; quickParsed = null; }}
						class="px-2 py-1 text-gray-500 hover:text-gray-700"
						aria-label="Cancel"
					>
						<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
						</svg>
					</button>
				</div>
			</div>
		{:else}
			<button
				onclick={() => (isAdding = true)}
				class="w-full text-left text-sm text-gray-500 hover:text-gray-700 hover:bg-gray-200 rounded px-2 py-1.5 transition-colors"
			>
				+ Add card
			</button>
		{/if}
	</div>
</div>
