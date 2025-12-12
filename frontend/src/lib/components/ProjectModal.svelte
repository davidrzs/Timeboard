<script lang="ts">
	import type { Project } from '../types';
	import { PROJECT_COLORS } from '../types';
	import { projects } from '../stores/projects';

	interface Props {
		project: Project | null;
		isOpen: boolean;
		onClose: () => void;
	}

	let { project, isOpen, onClose }: Props = $props();

	let name = $state('');
	let color = $state(PROJECT_COLORS[0]);

	$effect(() => {
		if (project) {
			name = project.name;
			color = project.color;
		} else {
			name = '';
			color = PROJECT_COLORS[0];
		}
	});

	async function handleSave() {
		if (!name.trim()) return;

		if (project) {
			await projects.update(project.id, { name, color });
		} else {
			await projects.create({ name, color });
		}

		onClose();
	}

	async function handleDelete() {
		if (!project) return;
		if (confirm('Delete this project? Tasks will be kept but unassigned.')) {
			await projects.delete(project.id);
			onClose();
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') onClose();
	}
</script>

{#if isOpen}
	<div
		class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
		onclick={onClose}
		onkeydown={handleKeydown}
		role="dialog"
		tabindex="-1"
	>
		<div
			class="bg-white rounded-xl shadow-2xl w-full max-w-sm"
			onclick={(e) => e.stopPropagation()}
			onkeydown={(e) => e.stopPropagation()}
			role="document"
		>
			<div class="p-4 border-b border-gray-100">
				<h2 class="text-lg font-medium">
					{project ? 'Edit Project' : 'New Project'}
				</h2>
			</div>

			<div class="p-4 space-y-4">
				<div>
					<label for="project-name" class="block text-sm text-gray-500 mb-1">Name</label>
					<input
						id="project-name"
						type="text"
						bind:value={name}
						placeholder="Project name"
						class="w-full text-sm border border-gray-200 rounded-lg px-3 py-2"
					/>
				</div>

				<div>
					<span class="block text-sm text-gray-500 mb-1">Color</span>
					<div class="flex gap-2 flex-wrap" role="listbox" aria-label="Project color">
						{#each PROJECT_COLORS as c}
							<button
								type="button"
								onclick={() => (color = c)}
								class="w-8 h-8 rounded-full border-2"
								style="background-color: {c}; border-color: {color === c ? '#1f2937' : 'transparent'}"
								aria-label="Select color {c}"
								aria-selected={color === c}
								role="option"
							></button>
						{/each}
					</div>
				</div>
			</div>

			<div class="p-4 border-t border-gray-100 flex justify-between">
				{#if project}
					<button
						onclick={handleDelete}
						class="px-4 py-2 text-sm text-red-600 hover:bg-red-50 rounded-lg"
					>
						Delete
					</button>
				{:else}
					<div></div>
				{/if}
				<div class="flex gap-2">
					<button
						onclick={onClose}
						class="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg"
					>
						Cancel
					</button>
					<button
						onclick={handleSave}
						class="px-4 py-2 text-sm bg-gray-900 text-white rounded-lg hover:bg-gray-800"
					>
						{project ? 'Save' : 'Create'}
					</button>
				</div>
			</div>
		</div>
	</div>
{/if}
