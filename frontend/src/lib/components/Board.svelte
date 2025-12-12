<script lang="ts">
	import { dndzone } from 'svelte-dnd-action';
	import type { Task, Project } from '../types';
	import { PROJECT_COLORS, TIME_HORIZONS } from '../types';
	import { tasksByProject, tasksByHorizon, tasks } from '../stores/tasks';
	import { projects, activeProjects } from '../stores/projects';
	import { groupBy, isDraggingTask, isOverFireZone } from '../stores/ui';
	import Column from './Column.svelte';

	// Fire zone ref
	let fireZoneRef = $state<HTMLDivElement | null>(null);

	function handleMouseMove(e: MouseEvent) {
		if (!$isDraggingTask || !fireZoneRef) {
			$isOverFireZone = false;
			return;
		}

		const rect = fireZoneRef.getBoundingClientRect();
		$isOverFireZone = e.clientY >= rect.top;
	}

	interface Props {
		onEditTask?: (task: Task) => void;
	}

	let { onEditTask }: Props = $props();

	let isAddingList = $state(false);
	let newListName = $state('');
	let newListColor = $state(PROJECT_COLORS[0]);
	let addListInputRef = $state<HTMLInputElement | null>(null);

	// For drag and drop of columns
	let projectColumns = $state<Project[]>([]);

	$effect(() => {
		projectColumns = [...$activeProjects];
	});

	$effect(() => {
		if (isAddingList && addListInputRef) {
			addListInputRef.focus();
		}
	});

	function handleColumnDndConsider(e: CustomEvent<{ items: Project[] }>) {
		projectColumns = e.detail.items;
	}

	async function handleColumnDndFinalize(e: CustomEvent<{ items: Project[] }>) {
		projectColumns = e.detail.items;
		const newOrder = projectColumns.map((p) => p.id);
		await projects.reorder(newOrder);
	}

	async function handleAddList() {
		if (!newListName.trim()) {
			isAddingList = false;
			return;
		}

		await projects.create({ name: newListName.trim(), color: newListColor });
		newListName = '';
		newListColor = PROJECT_COLORS[Math.floor(Math.random() * PROJECT_COLORS.length)];
		isAddingList = false;
	}

	function handleAddListKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') {
			e.preventDefault();
			handleAddList();
		} else if (e.key === 'Escape') {
			isAddingList = false;
			newListName = '';
		}
	}
</script>

<svelte:window onmousemove={handleMouseMove} />

<div class="flex-1 overflow-x-auto p-4 relative">
	{#if $groupBy === 'project'}
		<div class="flex gap-3 items-start">
			<div
				class="flex gap-3 items-start"
				use:dndzone={{
					items: projectColumns,
					flipDurationMs: 200,
					type: 'columns',
					dropTargetStyle: {}
				}}
				onconsider={handleColumnDndConsider}
				onfinalize={handleColumnDndFinalize}
			>
				{#each projectColumns as project (project.id)}
					<Column
						title={project.name}
						columnId={String(project.id)}
						items={$tasksByProject[project.id] || []}
						color={project.color}
						type="project"
						{project}
						{onEditTask}
					/>
				{/each}
			</div>

			<!-- Add List button/form -->
			{#if isAddingList}
				<div class="bg-gray-100 rounded-lg p-2 min-w-[272px]">
					<input
						bind:this={addListInputRef}
						bind:value={newListName}
						onkeydown={handleAddListKeydown}
						onblur={() => { if (!newListName.trim()) isAddingList = false; }}
						placeholder="Enter list name..."
						class="w-full text-sm px-2 py-1.5 rounded border-0 outline-none"
					/>
					<div class="flex items-center gap-2 mt-2">
						<div class="flex gap-1" role="listbox" aria-label="List color">
							{#each PROJECT_COLORS.slice(0, 6) as c}
								<button
									type="button"
									onclick={() => (newListColor = c)}
									class="w-5 h-5 rounded-full border-2"
									style="background-color: {c}; border-color: {newListColor === c ? '#1f2937' : 'transparent'}"
									aria-label="Select color {c}"
									aria-selected={newListColor === c}
									role="option"
								></button>
							{/each}
						</div>
						<div class="flex-1"></div>
						<button
							onclick={() => { isAddingList = false; newListName = ''; }}
							class="px-2 py-1 text-sm text-gray-500 hover:text-gray-700"
						>
							Cancel
						</button>
						<button
							onclick={handleAddList}
							class="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
						>
							Add
						</button>
					</div>
				</div>
			{:else}
				<button
					onclick={() => (isAddingList = true)}
					class="flex items-center gap-2 px-3 py-2 text-sm text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg min-w-[272px] transition-colors"
				>
					<svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
					</svg>
					Add list
				</button>
			{/if}
		</div>
	{:else}
		<div class="flex gap-3">
			{#each TIME_HORIZONS as horizon}
				<Column
					title={horizon.label}
					columnId={horizon.value}
					items={$tasksByHorizon[horizon.value]}
					{onEditTask}
				/>
			{/each}
		</div>
	{/if}

	<!-- Delete zone - appears at bottom when dragging -->
	<div
		bind:this={fireZoneRef}
		class="fixed bottom-0 left-0 right-0 h-[15vh] transition-all duration-200 z-50 flex items-center justify-center pointer-events-none {$isDraggingTask ? 'opacity-100' : 'opacity-0'} {$isOverFireZone ? 'bg-red-500' : 'bg-red-400/80'}"
	>
		<div class="text-white font-medium text-lg {$isOverFireZone ? 'scale-110' : ''}">
			{$isOverFireZone ? 'Release to delete' : 'Drag here to delete'}
		</div>
	</div>
</div>
