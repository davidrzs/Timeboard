<script lang="ts">
	import { onMount } from 'svelte';
	import { tasks } from '../stores/tasks';
	import { weekStartsOn } from '../stores/settings';
	import type { Task, TimeHorizon, CalendarEvent, GoogleCalendar, CalendarSyncState } from '../types';
	import { TIME_HORIZONS } from '../types';
	import { api } from '../api';

	interface Props {
		onEditTask?: (task: Task) => void;
	}

	let { onEditTask }: Props = $props();

	const HOURS = Array.from({ length: 24 }, (_, i) => i); // 0-23 (midnight to 11pm)
	const HOUR_HEIGHT = 48;
	const STALE_THRESHOLD_MS = 15 * 60 * 1000; // 15 minutes

	let currentDate = $state(new Date());
	let scrollContainer: HTMLDivElement;
	let draggingTask = $state<Task | null>(null);
	let dropPreview = $state<{ day: Date; hour: number; half: boolean } | null>(null);
	let calendarEvents = $state<CalendarEvent[]>([]);
	let calendars = $state<GoogleCalendar[]>([]);
	let calendarColors = $derived(
		Object.fromEntries(calendars.map((c) => [c.id, c.color]))
	);
	let loadingEvents = $state(false);
	let syncStates = $state<CalendarSyncState[]>([]);
	let isSyncing = $state(false);
	let lastSyncTime = $state<Date | null>(null);

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

	// Scheduled tasks for calendar (includes completed)
	let scheduledTasks = $derived($tasks.filter((t) => t.scheduled_start));

	// Overdue tasks: scheduled in the past and not completed
	let overdueTasks = $derived.by(() => {
		const now = new Date();
		return $tasks.filter((t) => {
			if (!t.scheduled_start || t.completed) return false;
			const scheduledEnd = t.scheduled_end
				? new Date(t.scheduled_end)
				: new Date(new Date(t.scheduled_start).getTime() + (t.estimated_minutes || 30) * 60 * 1000);
			return scheduledEnd < now;
		});
	});

	async function toggleComplete(task: Task) {
		if (task.completed) {
			await tasks.uncomplete(task.id);
		} else {
			await tasks.complete(task.id);
		}
	}

	function formatEstimate(minutes: number | null): string {
		if (!minutes) return '30m';
		if (minutes < 60) return `${minutes}m`;
		const h = Math.floor(minutes / 60);
		const m = minutes % 60;
		return m > 0 ? `${h}h${m}m` : `${h}h`;
	}

	// Week helpers
	function getWeekStart(date: Date, startDay?: number): Date {
		const d = new Date(date);
		const dayOfWeek = d.getDay();
		const diff = (dayOfWeek - (startDay ?? $weekStartsOn) + 7) % 7;
		d.setDate(d.getDate() - diff);
		d.setHours(0, 0, 0, 0);
		return d;
	}

	function getWeekDays(date: Date): Date[] {
		const start = getWeekStart(date);
		return Array.from({ length: 7 }, (_, i) => {
			const d = new Date(start);
			d.setDate(d.getDate() + i);
			return d;
		});
	}

	function formatDayHeader(date: Date): { day: string; num: number } {
		return {
			day: date.toLocaleDateString('en-US', { weekday: 'short' }),
			num: date.getDate()
		};
	}

	function formatHour(hour: number): string {
		if (hour === 0) return '12 AM';
		if (hour < 12) return `${hour} AM`;
		if (hour === 12) return '12 PM';
		return `${hour - 12} PM`;
	}

	function isToday(date: Date): boolean {
		const today = new Date();
		return date.toDateString() === today.toDateString();
	}

	function prevWeek() {
		const d = new Date(currentDate);
		d.setDate(d.getDate() - 7);
		currentDate = d;
	}

	function nextWeek() {
		const d = new Date(currentDate);
		d.setDate(d.getDate() + 7);
		currentDate = d;
	}

	function goToday() {
		currentDate = new Date();
	}

	function formatWeekRange(date: Date): string {
		const start = getWeekStart(date);
		const end = new Date(start);
		end.setDate(end.getDate() + 6);

		const startMonth = start.toLocaleDateString('en-US', { month: 'short' });
		const endMonth = end.toLocaleDateString('en-US', { month: 'short' });
		const year = end.getFullYear();

		if (startMonth === endMonth) {
			return `${startMonth} ${start.getDate()} - ${end.getDate()}, ${year}`;
		}
		return `${startMonth} ${start.getDate()} - ${endMonth} ${end.getDate()}, ${year}`;
	}

	function isCurrentWeek(): boolean {
		const today = new Date();
		const weekStart = getWeekStart(currentDate);
		const weekEnd = new Date(weekStart);
		weekEnd.setDate(weekEnd.getDate() + 7);
		return today >= weekStart && today < weekEnd;
	}

	function getNowPosition(): number {
		const now = new Date();
		const hour = now.getHours() + now.getMinutes() / 60;
		return hour * HOUR_HEIGHT;
	}

	// Fetch user's Google calendars (for colors)
	async function fetchCalendars() {
		try {
			calendars = await api.calendar.listCalendars();
		} catch (e) {
			console.error('Failed to fetch calendars:', e);
			calendars = [];
		}
	}

	// Fetch cached calendar events for the current week
	async function fetchCalendarEvents() {
		const weekStart = getWeekStart(currentDate);
		const weekEnd = new Date(weekStart);
		weekEnd.setDate(weekEnd.getDate() + 7);

		const startStr = weekStart.toISOString().split('T')[0];
		const endStr = weekEnd.toISOString().split('T')[0];

		loadingEvents = true;
		try {
			calendarEvents = await api.calendar.listCachedEvents(startStr, endStr);
		} catch (e) {
			console.error('Failed to fetch calendar events:', e);
			calendarEvents = [];
		} finally {
			loadingEvents = false;
		}
	}

	// Trigger sync with Google Calendar
	async function triggerSync() {
		isSyncing = true;
		try {
			const results = await api.calendar.sync();
			lastSyncTime = new Date();

			// Update sync states
			syncStates = await api.calendar.listSyncStates();

			// Check for errors
			const errors = results.flatMap((r) => r.errors);
			if (errors.length > 0) {
				console.error('Sync errors:', errors);
			}

			// Refresh cached events
			await fetchCalendarEvents();
			// Also refresh calendar colors (in case new calendars were added)
			await fetchCalendars();
		} catch (e) {
			console.error('Sync failed:', e);
		} finally {
			isSyncing = false;
		}
	}

	// Check if sync is stale
	function isSyncStale(): boolean {
		if (syncStates.length === 0) return true;

		const latestSync = syncStates
			.filter((s) => s.is_enabled && s.last_synced_at)
			.map((s) => new Date(s.last_synced_at!).getTime())
			.sort((a, b) => b - a)[0];

		if (!latestSync) return true;
		return Date.now() - latestSync > STALE_THRESHOLD_MS;
	}

	// Format relative time
	function formatRelativeTime(date: Date): string {
		const seconds = Math.floor((Date.now() - date.getTime()) / 1000);
		if (seconds < 60) return 'just now';
		const minutes = Math.floor(seconds / 60);
		if (minutes < 60) return `${minutes}m ago`;
		const hours = Math.floor(minutes / 60);
		return `${hours}h ago`;
	}

	// Refetch events when week changes (reads from cache)
	$effect(() => {
		const _ = currentDate;
		fetchCalendarEvents();
	});

	function getEventStyle(event: CalendarEvent): { top: string; height: string } {
		const start = new Date(event.start);
		const end = new Date(event.end);
		const startHour = start.getHours() + start.getMinutes() / 60;
		const endHour = end.getHours() + end.getMinutes() / 60;
		const top = startHour * HOUR_HEIGHT;
		const height = (endHour - startHour) * HOUR_HEIGHT;
		return {
			top: `${top}px`,
			height: `${Math.max(height, 24)}px`
		};
	}

	function getTaskStyle(task: Task): { top: string; height: string } {
		const start = new Date(task.scheduled_start!);
		const startHour = start.getHours() + start.getMinutes() / 60;
		const durationHours = (task.estimated_minutes || 30) / 60;
		const top = startHour * HOUR_HEIGHT;
		const height = durationHours * HOUR_HEIGHT;
		return {
			top: `${top}px`,
			height: `${Math.max(height, 20)}px`
		};
	}

	interface LayoutedEvent {
		event: CalendarEvent;
		column: number;
		totalColumns: number;
	}

	function getEventsForDay(date: Date, events: CalendarEvent[]): LayoutedEvent[] {
		const dayEvents = events.filter((e) => {
			const eventStart = new Date(e.start);
			return eventStart.toDateString() === date.toDateString();
		});

		// Sort by start time, then by duration (longer first)
		dayEvents.sort((a, b) => {
			const startDiff = new Date(a.start).getTime() - new Date(b.start).getTime();
			if (startDiff !== 0) return startDiff;
			const aDuration = new Date(a.end).getTime() - new Date(a.start).getTime();
			const bDuration = new Date(b.end).getTime() - new Date(b.start).getTime();
			return bDuration - aDuration;
		});

		// Check if two events overlap
		function overlaps(a: CalendarEvent, b: CalendarEvent): boolean {
			const aStart = new Date(a.start).getTime();
			const aEnd = new Date(a.end).getTime();
			const bStart = new Date(b.start).getTime();
			const bEnd = new Date(b.end).getTime();
			return aStart < bEnd && bStart < aEnd;
		}

		// Assign columns to events
		const layouted: LayoutedEvent[] = [];
		const columns: CalendarEvent[][] = [];

		for (const event of dayEvents) {
			// Find first column where this event doesn't overlap with existing events
			let placed = false;
			for (let col = 0; col < columns.length; col++) {
				const canPlace = columns[col].every((e) => !overlaps(e, event));
				if (canPlace) {
					columns[col].push(event);
					layouted.push({ event, column: col, totalColumns: 0 });
					placed = true;
					break;
				}
			}
			if (!placed) {
				columns.push([event]);
				layouted.push({ event, column: columns.length - 1, totalColumns: 0 });
			}
		}

		// Calculate total columns for each event (max columns among overlapping events)
		for (const item of layouted) {
			const overlappingEvents = layouted.filter((other) => overlaps(item.event, other.event));
			const maxCol = Math.max(...overlappingEvents.map((e) => e.column)) + 1;
			item.totalColumns = maxCol;
		}

		return layouted;
	}

	function getTasksForDay(date: Date): Task[] {
		return scheduledTasks.filter((t) => {
			const start = new Date(t.scheduled_start!);
			return start.toDateString() === date.toDateString();
		});
	}

	// Drag and drop
	function handleDragStart(e: DragEvent, task: Task) {
		draggingTask = task;
		if (e.dataTransfer) {
			e.dataTransfer.effectAllowed = 'move';
			e.dataTransfer.setData('text/plain', task.id.toString());
		}
	}

	function handleDragEnd() {
		draggingTask = null;
		dropPreview = null;
	}

	function handleSlotDragOver(e: DragEvent, day: Date, hour: number, half: boolean) {
		e.preventDefault();
		if (e.dataTransfer) e.dataTransfer.dropEffect = 'move';
		dropPreview = { day, hour, half };
	}

	function handleSlotDragLeave() {
		dropPreview = null;
	}

	async function handleSlotDrop(e: DragEvent, day: Date, hour: number, half: boolean) {
		e.preventDefault();
		if (!draggingTask) return;

		const minutes = half ? 30 : 0;
		const start = new Date(day);
		start.setHours(hour, minutes, 0, 0);

		const duration = draggingTask.estimated_minutes || 30;
		const end = new Date(start.getTime() + duration * 60 * 1000);

		await tasks.update(draggingTask.id, {
			scheduled_start: start.toISOString(),
			scheduled_end: end.toISOString()
		});

		draggingTask = null;
		dropPreview = null;
	}

	function isDropTarget(day: Date, hour: number, half: boolean): boolean {
		if (!dropPreview) return false;
		return (
			dropPreview.day.toDateString() === day.toDateString() &&
			dropPreview.hour === hour &&
			dropPreview.half === half
		);
	}

	onMount(async () => {
		if (scrollContainer) {
			const now = new Date();
			const scrollTo = Math.max(0, (now.getHours() - 1) * HOUR_HEIGHT);
			scrollContainer.scrollTop = scrollTo;
		}

		// Fetch calendars for colors
		await fetchCalendars();

		// Get sync states
		try {
			syncStates = await api.calendar.listSyncStates();
		} catch (e) {
			console.error('Failed to fetch sync states:', e);
		}

		// Trigger sync if stale
		if (isSyncStale()) {
			await triggerSync();
		} else {
			// Just fetch from cache
			await fetchCalendarEvents();
		}
	});

	let weekDays = $derived(getWeekDays(currentDate));
	let nowPosition = $derived(getNowPosition());
</script>

<div class="flex h-full bg-white overflow-hidden">
	<!-- Left sidebar: Unscheduled tasks -->
	<div class="w-64 border-r border-gray-200 bg-gray-50 overflow-y-auto flex-shrink-0">
		<div class="p-3">
			{#if overdueTasks.length > 0}
				<div class="mb-4">
					<h3 class="text-xs font-medium text-red-500 uppercase tracking-wide mb-2">
						Overdue
						<span class="text-red-300">({overdueTasks.length})</span>
					</h3>
					<div class="space-y-1.5">
						{#each overdueTasks as task}
							<div
								draggable="true"
								ondragstart={(e) => handleDragStart(e, task)}
								ondragend={handleDragEnd}
								ondblclick={() => onEditTask?.(task)}
								onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onEditTask?.(task); } }}
								role="button"
								tabindex="0"
								class="bg-red-50 border border-red-200 rounded px-2 py-1.5 cursor-grab hover:border-red-300 hover:shadow-sm transition-all active:cursor-grabbing"
								class:opacity-50={draggingTask?.id === task.id}
							>
								<div class="flex items-start gap-2">
									<button
										onclick={(e) => { e.stopPropagation(); toggleComplete(task); }}
										class="w-3.5 h-3.5 mt-0.5 flex-shrink-0 rounded border-[1.5px] border-red-400 flex items-center justify-center"
										aria-label="Mark as complete"
									></button>
									<div class="flex-1 min-w-0">
										<p class="text-sm text-gray-800 truncate">{task.title}</p>
										<p class="text-xs text-red-400">{formatEstimate(task.estimated_minutes)}</p>
									</div>
								</div>
							</div>
						{/each}
					</div>
				</div>
			{/if}

			<h2 class="text-sm font-medium text-gray-700 mb-3">Unscheduled</h2>

			{#each TIME_HORIZONS as horizon}
				{@const tasksInHorizon = unscheduledByHorizon[horizon.value]}
				{#if tasksInHorizon.length > 0}
					<div class="mb-4">
						<h3 class="text-xs font-medium text-gray-400 uppercase tracking-wide mb-2">
							{horizon.label}
							<span class="text-gray-300">({tasksInHorizon.length})</span>
						</h3>
						<div class="space-y-1.5">
							{#each tasksInHorizon as task}
								<div
									draggable="true"
									ondragstart={(e) => handleDragStart(e, task)}
									ondragend={handleDragEnd}
									ondblclick={() => onEditTask?.(task)}
									onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onEditTask?.(task); } }}
									role="button"
									tabindex="0"
									class="bg-white border border-gray-200 rounded px-2 py-1.5 cursor-grab hover:border-gray-300 hover:shadow-sm transition-all active:cursor-grabbing"
									class:opacity-50={draggingTask?.id === task.id}
								>
									<div class="flex items-start gap-2">
										{#if task.project}
											<span
												class="w-2 h-2 rounded-full flex-shrink-0 mt-1"
												style="background-color: {task.project.color}"
											></span>
										{/if}
										<div class="flex-1 min-w-0">
											<p class="text-sm text-gray-800 truncate">{task.title}</p>
											<p class="text-xs text-gray-400">{formatEstimate(task.estimated_minutes)}</p>
										</div>
									</div>
								</div>
							{/each}
						</div>
					</div>
				{/if}
			{/each}

			{#if Object.values(unscheduledByHorizon).every((arr) => arr.length === 0)}
				<p class="text-sm text-gray-400 text-center py-8">All tasks scheduled</p>
			{/if}
		</div>
	</div>

	<!-- Right: Calendar -->
	<div class="flex-1 flex flex-col overflow-hidden">
		<!-- Header -->
		<div class="flex items-center justify-between px-4 py-2 border-b border-gray-200">
			<div class="flex items-center gap-1">
				<button
					onclick={prevWeek}
					class="p-1.5 rounded hover:bg-gray-100 text-gray-500 hover:text-gray-700"
					aria-label="Previous week"
				>
					<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
					</svg>
				</button>
				<button
					onclick={nextWeek}
					class="p-1.5 rounded hover:bg-gray-100 text-gray-500 hover:text-gray-700"
					aria-label="Next week"
				>
					<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
					</svg>
				</button>
				<button
					onclick={goToday}
					class="ml-1 px-2 py-1 text-xs rounded hover:bg-gray-100 text-gray-600"
				>
					Today
				</button>
			</div>
			<h2 class="text-sm font-medium text-gray-800">{formatWeekRange(currentDate)}</h2>
			<div class="flex items-center gap-2">
				{#if lastSyncTime}
					<span class="text-xs text-gray-400">
						{formatRelativeTime(lastSyncTime)}
					</span>
				{/if}
				<button
					onclick={triggerSync}
					disabled={isSyncing}
					class="p-1.5 rounded hover:bg-gray-100 text-gray-500 hover:text-gray-700 disabled:opacity-50"
					title="Sync calendars"
				>
					<svg
						class="w-4 h-4"
						class:animate-spin={isSyncing}
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
					>
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
					</svg>
				</button>
			</div>
		</div>

		<!-- Day headers -->
		<div class="grid grid-cols-[3rem_repeat(7,1fr)] border-b border-gray-100 bg-gray-50">
			<div></div>
			{#each weekDays as day}
				{@const header = formatDayHeader(day)}
				<div class="py-2 text-center border-l border-gray-100">
					<div class="text-[11px] uppercase tracking-wide text-gray-400 font-medium">{header.day}</div>
					<div
						class="text-sm font-medium mt-0.5 w-7 h-7 mx-auto flex items-center justify-center rounded-full {isToday(day) ? 'bg-blue-600 text-white' : 'text-gray-700'}"
					>
						{header.num}
					</div>
				</div>
			{/each}
		</div>

		<!-- Time grid -->
		<div class="flex-1 overflow-auto" bind:this={scrollContainer}>
			<div class="grid grid-cols-[3rem_repeat(7,1fr)] relative" style="height: {HOURS.length * HOUR_HEIGHT}px">
				<!-- Time labels -->
				<div class="relative bg-white">
					{#each HOURS as hour, i}
						<div
							class="absolute right-2 text-[10px] text-gray-400 -translate-y-1/2"
							style="top: {i * HOUR_HEIGHT}px"
						>
							{formatHour(hour)}
						</div>
					{/each}
				</div>

				<!-- Day columns -->
				{#each weekDays as day}
					<div class="relative border-l border-gray-100" style:background={isToday(day) ? '#fffbeb' : ''}>
						<!-- Hour slots (drop zones) -->
						{#each HOURS as hour, i}
							<!-- Full hour line -->
							<div
								class="absolute left-0 right-0 border-t border-gray-200"
								style="top: {i * HOUR_HEIGHT}px"
							></div>
							<!-- Half hour line -->
							<div
								class="absolute left-0 right-0 border-t border-dashed border-gray-100"
								style="top: {i * HOUR_HEIGHT + HOUR_HEIGHT / 2}px"
							></div>

							<!-- Drop zones: first half -->
							<div
								role="presentation"
								class="absolute left-0 right-0 z-10"
								style="top: {i * HOUR_HEIGHT}px; height: {HOUR_HEIGHT / 2}px"
								ondragover={(e) => handleSlotDragOver(e, day, hour, false)}
								ondragleave={handleSlotDragLeave}
								ondrop={(e) => handleSlotDrop(e, day, hour, false)}
								class:bg-blue-100={isDropTarget(day, hour, false)}
								class:opacity-50={isDropTarget(day, hour, false)}
							></div>
							<!-- Drop zones: second half -->
							<div
								role="presentation"
								class="absolute left-0 right-0 z-10"
								style="top: {i * HOUR_HEIGHT + HOUR_HEIGHT / 2}px; height: {HOUR_HEIGHT / 2}px"
								ondragover={(e) => handleSlotDragOver(e, day, hour, true)}
								ondragleave={handleSlotDragLeave}
								ondrop={(e) => handleSlotDrop(e, day, hour, true)}
								class:bg-blue-100={isDropTarget(day, hour, true)}
								class:opacity-50={isDropTarget(day, hour, true)}
							></div>
						{/each}

						<!-- Google Calendar events (read-only) -->
						{#each getEventsForDay(day, calendarEvents) as { event, column, totalColumns }}
							{@const style = getEventStyle(event)}
							{@const color = calendarColors[event.calendar_id] || '#9ca3af'}
							{@const width = `calc((100% - 8px) / ${totalColumns})`}
							{@const left = `calc(4px + (100% - 8px) * ${column} / ${totalColumns})`}
							<div
								class="absolute px-1.5 py-1 rounded border-l-[3px] text-xs overflow-hidden z-20"
								style="top: {style.top}; height: {style.height}; width: {width}; left: {left}; background-color: {color}20; border-left-color: {color}; color: {color}"
								title={event.location ? `${event.title}\n${event.location}` : event.title}
							>
								<div class="font-medium truncate leading-tight" style="color: inherit">{event.title}</div>
								{#if event.location && parseFloat(style.height) >= 36}
									<div class="text-[10px] opacity-70 truncate">{event.location}</div>
								{/if}
							</div>
						{/each}

						<!-- Scheduled tasks (draggable) -->
						{#each getTasksForDay(day) as task}
							{@const style = getTaskStyle(task)}
							{@const taskColor = task.project?.color || '#3b82f6'}
							{@const stripeColor = task.completed ? '#e5e7eb' : taskColor + '15'}
							{@const bgColor = task.completed ? '#f9fafb' : taskColor + '08'}
							<div
								draggable="true"
								ondragstart={(e) => handleDragStart(e, task)}
								ondragend={handleDragEnd}
								ondblclick={() => onEditTask?.(task)}
								onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onEditTask?.(task); } }}
								role="button"
								tabindex="0"
								class="absolute left-1 right-1 px-2 py-1 rounded border-l-[3px] text-xs overflow-hidden cursor-grab z-20 shadow-sm hover:shadow"
								style="top: {style.top}; height: {style.height}; background: repeating-linear-gradient(135deg, {bgColor}, {bgColor} 4px, {stripeColor} 4px, {stripeColor} 5px); border-left-color: {task.completed ? '#9ca3af' : taskColor}; color: {task.completed ? '#9ca3af' : taskColor}"
								class:opacity-50={draggingTask?.id === task.id}
							>
								<div class="flex items-start gap-1.5">
									<button
										onclick={(e) => { e.stopPropagation(); toggleComplete(task); }}
										class="w-3.5 h-3.5 mt-0.5 flex-shrink-0 rounded border-[1.5px] flex items-center justify-center transition-colors"
										style="border-color: {task.completed ? '#9ca3af' : taskColor}; background-color: {task.completed ? '#9ca3af' : 'transparent'}"
									>
										{#if task.completed}
											<svg class="w-2 h-2 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="3">
												<path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
											</svg>
										{/if}
									</button>
									<div class="flex-1 min-w-0">
										<div class="font-medium truncate leading-tight" class:line-through={task.completed}>{task.title}</div>
										{#if parseFloat(style.height) >= 36}
											<div class="text-[10px] opacity-70 mt-0.5">
												{formatEstimate(task.estimated_minutes)}
											</div>
										{/if}
									</div>
								</div>
							</div>
						{/each}

						<!-- Now indicator -->
						{#if isToday(day) && isCurrentWeek()}
							<div
								class="absolute left-0 right-0 z-30 pointer-events-none"
								style="top: {nowPosition}px"
							>
								<div class="absolute -left-1.5 -top-1.5 w-3 h-3 rounded-full bg-red-500"></div>
								<div class="border-t-2 border-red-500"></div>
							</div>
						{/if}
					</div>
				{/each}
			</div>
		</div>
	</div>
</div>
