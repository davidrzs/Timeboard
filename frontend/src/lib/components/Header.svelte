<script lang="ts">
	import { auth } from '../stores/auth';
	import { quickAddOpen, groupBy, showCalendar, settingsModalOpen } from '../stores/ui';

	function handleKeydown(e: KeyboardEvent) {
		if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
			e.preventDefault();
			$quickAddOpen = true;
		}
	}
</script>

<svelte:window onkeydown={handleKeydown} />

<header class="bg-white border-b border-gray-200 px-4 py-3">
	<div class="flex items-center justify-between">
		<div class="flex items-center gap-6">
			<h1 class="text-xl font-semibold text-gray-900">Timeboard</h1>

			<div data-tour="view-toggle" class="flex items-center gap-1 bg-gray-100 rounded-lg p-0.5">
				<button
					onclick={() => ($showCalendar = false)}
					class="px-3 py-1 text-sm rounded-md transition-colors"
					class:bg-white={!$showCalendar}
					class:shadow-sm={!$showCalendar}
					class:text-gray-900={!$showCalendar}
					class:text-gray-500={$showCalendar}
				>
					Board
				</button>
				<button
					onclick={() => ($showCalendar = true)}
					class="px-3 py-1 text-sm rounded-md transition-colors"
					class:bg-white={$showCalendar}
					class:shadow-sm={$showCalendar}
					class:text-gray-900={$showCalendar}
					class:text-gray-500={!$showCalendar}
				>
					Calendar
				</button>
			</div>

			{#if !$showCalendar}
				<div data-tour="group-toggle" class="flex items-center gap-1 bg-gray-100 rounded-lg p-0.5">
					<button
						onclick={() => ($groupBy = 'project')}
						class="px-3 py-1 text-sm rounded-md transition-colors"
						class:bg-white={$groupBy === 'project'}
						class:shadow-sm={$groupBy === 'project'}
						class:text-gray-900={$groupBy === 'project'}
						class:text-gray-500={$groupBy !== 'project'}
					>
						Lists
					</button>
					<button
						onclick={() => ($groupBy = 'time')}
						class="px-3 py-1 text-sm rounded-md transition-colors"
						class:bg-white={$groupBy === 'time'}
						class:shadow-sm={$groupBy === 'time'}
						class:text-gray-900={$groupBy === 'time'}
						class:text-gray-500={$groupBy !== 'time'}
					>
						Timeline
					</button>
				</div>
			{/if}
		</div>

		<div class="flex items-center gap-4">
			<button
				data-tour="quick-add"
				onclick={() => ($quickAddOpen = true)}
				class="flex items-center gap-2 px-3 py-1.5 text-sm text-gray-600 bg-gray-100 rounded-lg hover:bg-gray-200"
			>
				<span>Quick Add</span>
				<kbd class="text-xs bg-gray-200 px-1.5 py-0.5 rounded">Cmd+K</kbd>
			</button>

			{#if $auth.user}
				<div class="flex items-center gap-3">
					<button
						onclick={() => ($settingsModalOpen = true)}
						class="p-1.5 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg"
						aria-label="Settings"
					>
						<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"></path>
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path>
						</svg>
					</button>
					<span class="text-sm text-gray-600">{$auth.user.email}</span>
					<button
						onclick={() => auth.logout()}
						class="text-sm text-gray-500 hover:text-gray-700"
					>
						Logout
					</button>
				</div>
			{/if}
		</div>
	</div>
</header>
