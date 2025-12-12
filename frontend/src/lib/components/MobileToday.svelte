<script lang="ts">
	import { onMount } from 'svelte';
	import type { Task, CalendarEvent, GoogleCalendar, TimeHorizon } from '../types';
	import { TIME_HORIZONS } from '../types';
	import { tasks } from '../stores/tasks';
	import { quickAddOpen } from '../stores/ui';
	import { api } from '../api';
	import TaskCard from './TaskCard.svelte';

	interface Props {
		onEditTask?: (task: Task) => void;
	}

	let { onEditTask }: Props = $props();

	// Today's scheduled tasks for timeline
	let todayScheduled = $derived.by(() => {
		const today = new Date();
		return $tasks
			.filter((t) => {
				if (!t.scheduled_start || t.completed) return false;
				const start = new Date(t.scheduled_start);
				return start.toDateString() === today.toDateString();
			})
			.sort((a, b) => new Date(a.scheduled_start!).getTime() - new Date(b.scheduled_start!).getTime());
	});

	// Unscheduled tasks grouped by horizon
	let unscheduledByHorizon = $derived.by(() => {
		const grouped: Record<TimeHorizon, Task[]> = {
			today: [],
			this_week: [],
			next_week: [],
			later: [],
			backlog: []
		};

		for (const task of $tasks) {
			if (!task.completed && !task.scheduled_start) {
				const horizon = task.time_horizon || 'backlog';
				if (grouped[horizon]) {
					grouped[horizon].push(task);
				}
			}
		}

		for (const horizon of Object.keys(grouped) as TimeHorizon[]) {
			grouped[horizon].sort((a, b) => a.position - b.position);
		}

		return grouped;
	});

	// Calendar events
	let calendarEvents = $state<CalendarEvent[]>([]);
	let calendars = $state<GoogleCalendar[]>([]);
	let calendarColors = $derived(
		Object.fromEntries(calendars.map((c) => [c.id, c.color]))
	);

	// Filter to today's events only
	let todayEvents = $derived.by(() => {
		const today = new Date();
		return calendarEvents.filter((e) => {
			const eventStart = new Date(e.start);
			return eventStart.toDateString() === today.toDateString();
		}).sort((a, b) => new Date(a.start).getTime() - new Date(b.start).getTime());
	});

	// Timeline spans 6am to 10pm (16 hours)
	const TIMELINE_START = 6;
	const TIMELINE_END = 22;
	const TIMELINE_HOURS = TIMELINE_END - TIMELINE_START;
	const HOUR_WIDTH = 60; // pixels per hour

	function getTaskPosition(task: Task): { left: number; width: number } {
		if (!task.scheduled_start) return { left: 0, width: 0 };

		const start = new Date(task.scheduled_start);
		const startHour = start.getHours() + start.getMinutes() / 60;

		let endHour: number;
		if (task.scheduled_end) {
			const end = new Date(task.scheduled_end);
			endHour = end.getHours() + end.getMinutes() / 60;
		} else if (task.estimated_minutes) {
			endHour = startHour + task.estimated_minutes / 60;
		} else {
			endHour = startHour + 0.5; // default 30 min
		}

		const left = Math.max(0, (startHour - TIMELINE_START) * HOUR_WIDTH);
		const width = Math.max(30, (endHour - startHour) * HOUR_WIDTH);

		return { left, width };
	}

	function getEventPosition(event: CalendarEvent): { left: number; width: number } {
		const start = new Date(event.start);
		const end = new Date(event.end);
		const startHour = start.getHours() + start.getMinutes() / 60;
		const endHour = end.getHours() + end.getMinutes() / 60;

		const left = Math.max(0, (startHour - TIMELINE_START) * HOUR_WIDTH);
		const width = Math.max(30, (endHour - startHour) * HOUR_WIDTH);

		return { left, width };
	}

	function formatHour(hour: number): string {
		if (hour === 12) return '12p';
		if (hour > 12) return `${hour - 12}p`;
		return `${hour}a`;
	}

	function getCurrentTimePosition(): number {
		const now = new Date();
		const currentHour = now.getHours() + now.getMinutes() / 60;
		return (currentHour - TIMELINE_START) * HOUR_WIDTH;
	}

	let nowPosition = $state(getCurrentTimePosition());

	$effect(() => {
		const interval = setInterval(() => {
			nowPosition = getCurrentTimePosition();
		}, 60000);
		return () => clearInterval(interval);
	});

	async function fetchCalendarData() {
		try {
			// Get calendars for colors
			calendars = await api.calendar.listCalendars();

			// Get today's events
			const today = new Date();
			const startStr = today.toISOString().split('T')[0];
			const tomorrow = new Date(today);
			tomorrow.setDate(tomorrow.getDate() + 1);
			const endStr = tomorrow.toISOString().split('T')[0];

			calendarEvents = await api.calendar.listCachedEvents(startStr, endStr);
		} catch (e) {
			console.error('Failed to fetch calendar data:', e);
		}
	}

	onMount(() => {
		fetchCalendarData();
	});
</script>

<div class="flex flex-col h-full bg-gray-50">
	<!-- Timeline header -->
	<div class="bg-white border-b px-4 py-2">
		<h2 class="text-sm font-medium text-gray-500">Today's Schedule</h2>
	</div>

	<!-- Horizontal timeline -->
	<div class="bg-white border-b overflow-x-auto">
		<div class="relative h-32" style="width: {TIMELINE_HOURS * HOUR_WIDTH}px; min-width: 100%;">
			<!-- Hour markers -->
			<div class="absolute top-0 left-0 right-0 h-6 flex border-b border-gray-100">
				{#each Array(TIMELINE_HOURS) as _, i}
					<div
						class="flex-shrink-0 text-xs text-gray-400 pl-1 border-l border-gray-100"
						style="width: {HOUR_WIDTH}px"
					>
						{formatHour(TIMELINE_START + i)}
					</div>
				{/each}
			</div>

			<!-- Current time indicator -->
			{#if nowPosition >= 0 && nowPosition <= TIMELINE_HOURS * HOUR_WIDTH}
				<div
					class="absolute top-6 bottom-0 w-0.5 bg-red-500 z-20"
					style="left: {nowPosition}px"
				>
					<div class="w-2 h-2 bg-red-500 rounded-full -ml-[3px] -mt-1"></div>
				</div>
			{/if}

			<!-- Calendar events (top row) -->
			<div class="absolute top-7 left-0 right-0 h-11 px-1">
				{#each todayEvents as event}
					{@const pos = getEventPosition(event)}
					{@const color = calendarColors[event.calendar_id] || '#9ca3af'}
					<div
						class="absolute top-0 h-10 rounded px-2 py-1 overflow-hidden border-l-2"
						style="left: {pos.left}px; width: {pos.width}px; background-color: {color}20; border-left-color: {color}"
					>
						<div class="text-xs font-medium truncate" style="color: {color}">{event.title}</div>
						<div class="text-[10px] text-gray-500">
							{new Date(event.start).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}
						</div>
					</div>
				{/each}
			</div>

			<!-- Scheduled tasks (bottom row) -->
			<div class="absolute top-[4.75rem] left-0 right-0 h-11 px-1">
				{#each todayScheduled as task}
					{@const pos = getTaskPosition(task)}
					<button
						class="absolute top-0 h-10 rounded px-2 py-1 text-left overflow-hidden shadow-sm hover:shadow transition-shadow border-l-2"
						style="left: {pos.left}px; width: {pos.width}px; background-color: {task.project?.color || '#3B82F6'}20; border-left-color: {task.project?.color || '#3B82F6'}"
						onclick={() => onEditTask?.(task)}
					>
						<div class="text-xs font-medium text-gray-800 truncate">{task.title}</div>
						{#if task.scheduled_start}
							<div class="text-[10px] text-gray-500">
								{new Date(task.scheduled_start).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}
							</div>
						{/if}
					</button>
				{/each}
			</div>

			<!-- Empty state -->
			{#if todayScheduled.length === 0 && todayEvents.length === 0}
				<div class="absolute top-10 left-0 right-0 flex items-center justify-center text-sm text-gray-400">
					Nothing scheduled
				</div>
			{/if}
		</div>
	</div>

	<!-- Task list grouped by horizon -->
	<div class="flex-1 overflow-y-auto pb-24">
		{#each TIME_HORIZONS as horizon}
			{@const tasksInHorizon = unscheduledByHorizon[horizon.value]}
			{#if tasksInHorizon.length > 0}
				<div class="border-b border-gray-200 last:border-b-0">
					<div class="px-4 py-2 bg-gray-50 sticky top-0">
						<h2 class="text-sm font-medium text-gray-500">
							{horizon.label}
							<span class="text-gray-400">({tasksInHorizon.length})</span>
						</h2>
					</div>
					<div class="px-4 py-2 space-y-2">
						{#each tasksInHorizon as task (task.id)}
							<TaskCard {task} onEdit={onEditTask} />
						{/each}
					</div>
				</div>
			{/if}
		{/each}

		{#if Object.values(unscheduledByHorizon).every((arr) => arr.length === 0)}
			<div class="text-center text-gray-400 py-8">
				No tasks
			</div>
		{/if}
	</div>

	<!-- FAB -->
	<button
		onclick={() => quickAddOpen.set(true)}
		class="fixed bottom-6 right-6 w-14 h-14 bg-blue-600 hover:bg-blue-700 text-white rounded-full shadow-lg flex items-center justify-center text-2xl font-light transition-colors z-50"
		aria-label="Add task"
	>
		<svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
			<path stroke-linecap="round" stroke-linejoin="round" d="M12 4v16m8-8H4" />
		</svg>
	</button>
</div>
