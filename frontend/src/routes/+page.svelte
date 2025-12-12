<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api';
	import { auth } from '$lib/stores/auth';
	import { projects } from '$lib/stores/projects';
	import { tasks } from '$lib/stores/tasks';
	import { settings } from '$lib/stores/settings';
	import { showCalendar } from '$lib/stores/ui';
	import { startTour } from '$lib/tour';
	import Header from '$lib/components/Header.svelte';
	import Board from '$lib/components/Board.svelte';
	import Calendar from '$lib/components/Calendar.svelte';
	import MobileToday from '$lib/components/MobileToday.svelte';
	import QuickAddModal from '$lib/components/QuickAddModal.svelte';
	import TaskEditModal from '$lib/components/TaskEditModal.svelte';
	import PlanModal from '$lib/components/PlanModal.svelte';
	import SettingsModal from '$lib/components/SettingsModal.svelte';

	const MOBILE_BREAKPOINT = 768;

	let editingTaskId = $state<number | null>(null);
	let loading = $state(true);
	let isMobile = $state(false);

	$effect(() => {
		const checkMobile = () => {
			isMobile = window.innerWidth < MOBILE_BREAKPOINT;
		};
		checkMobile();
		window.addEventListener('resize', checkMobile);
		return () => window.removeEventListener('resize', checkMobile);
	});

	onMount(async () => {
		try {
			const user = await auth.check();
			if (user) {
				const [, , userSettings] = await Promise.all([
					projects.load(),
					tasks.load(),
					settings.load()
				]);
				if (!userSettings.has_seen_tour) {
					setTimeout(() => startTour(), 500);
				}
			}
		} finally {
			loading = false;
		}
	});

</script>

{#if loading}
	<div class="min-h-screen flex items-center justify-center">
		<p class="text-gray-500">Loading...</p>
	</div>
{:else if !$auth.user}
	<div class="min-h-screen flex items-center justify-center bg-gray-50">
		<div class="text-center">
			<h1 class="text-2xl font-semibold text-gray-900 mb-4">Timeboard</h1>
			<p class="text-gray-500 mb-6">Sign in to manage your tasks</p>
			<button
				onclick={() => auth.googleLogin()}
				class="flex items-center justify-center gap-2 px-6 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
			>
				<svg class="w-5 h-5" viewBox="0 0 24 24">
					<path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
					<path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
					<path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
					<path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
				</svg>
				Sign in with Google
			</button>
		</div>
	</div>
{:else}
	<div class="h-screen flex flex-col overflow-hidden">
		{#if isMobile}
			<MobileToday onEditTask={(task) => (editingTaskId = task.id)} />
		{:else}
			<Header />
			{#if $showCalendar}
				<Calendar onEditTask={(task) => (editingTaskId = task.id)} />
			{:else}
				<div class="flex-1 overflow-auto">
					<Board onEditTask={(task) => (editingTaskId = task.id)} />
				</div>
			{/if}
		{/if}
	</div>

	<QuickAddModal />
	<TaskEditModal taskId={editingTaskId} onClose={() => (editingTaskId = null)} />
	<PlanModal />
	<SettingsModal />
{/if}
