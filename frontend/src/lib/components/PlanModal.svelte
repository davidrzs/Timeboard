<script lang="ts">
	import { planModalOpen } from '../stores/ui';
	import { tasks } from '../stores/tasks';
	import { api } from '../api';
	import type { ProposedPlan, TimeSlot, CalendarEvent, Task } from '../types';
	import { dndzone } from 'svelte-dnd-action';
	import { flip } from 'svelte/animate';
	import { get } from 'svelte/store';

	interface ScheduleSlot extends TimeSlot {
		id: string;
		title: string;
		end_time: string;
	}

	let loading = $state(false);
	let error = $state<string | null>(null);
	let plan = $state<ProposedPlan | null>(null);
	let schedule = $state<ScheduleSlot[]>([]);
	let calendarEvents = $state<CalendarEvent[]>([]);
	let committing = $state(false);

	// Timeline config
	const DAY_START_HOUR = 7;
	const DAY_END_HOUR = 22;
	const HOUR_HEIGHT = 48; // pixels per hour

	function getTaskTitle(taskId: number): string {
		const tasksList = get(tasks);
		const task = tasksList.find((t: Task) => t.id === taskId);
		return task?.title || `Task #${taskId}`;
	}

	function calcEndTime(startTime: string, minutes: number): string {
		const [hours, mins] = startTime.split(':').map(Number);
		const endMinutes = hours * 60 + mins + minutes;
		const endH = Math.floor(endMinutes / 60);
		const endM = endMinutes % 60;
		return `${String(endH).padStart(2, '0')}:${String(endM).padStart(2, '0')}`;
	}

	async function generatePlan() {
		loading = true;
		error = null;
		try {
			// Fetch calendar events for today
			const today = new Date().toISOString().split('T')[0];
			const [planResult, eventsResult] = await Promise.all([
				api.llm.generateSchedule(),
				api.calendar.listCachedEvents(today, today)
			]);
			plan = planResult;
			calendarEvents = eventsResult;
			schedule = plan.schedule.map((slot) => ({
				...slot,
				id: `slot-${slot.task_id}`,
				title: getTaskTitle(slot.task_id),
				end_time: calcEndTime(slot.start_time, slot.estimated_minutes)
			}));
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to generate plan';
		} finally {
			loading = false;
		}
	}

	function handleDndConsider(e: CustomEvent<{ items: ScheduleSlot[] }>) {
		schedule = e.detail.items;
	}

	function handleDndFinalize(e: CustomEvent<{ items: ScheduleSlot[] }>) {
		const newItems = e.detail.items;
		// Recalculate times after reorder
		let currentTime = newItems[0]?.start_time || '09:00';

		schedule = newItems.map((slot) => {
			const startTime = currentTime;
			const [hours, minutes] = startTime.split(':').map(Number);
			const endMinutes = hours * 60 + minutes + slot.estimated_minutes;
			const endHours = Math.floor(endMinutes / 60);
			const endMins = endMinutes % 60;
			const endTime = `${String(endHours).padStart(2, '0')}:${String(endMins).padStart(2, '0')}`;

			currentTime = endTime;

			return { ...slot, start_time: startTime, end_time: endTime };
		});
	}

	function timeToPosition(time: string): number {
		const [hours, minutes] = time.split(':').map(Number);
		const totalMinutes = (hours - DAY_START_HOUR) * 60 + minutes;
		return (totalMinutes / 60) * HOUR_HEIGHT;
	}

	function durationToHeight(startTime: string, endTime: string): number {
		const [startH, startM] = startTime.split(':').map(Number);
		const [endH, endM] = endTime.split(':').map(Number);
		const durationMinutes = (endH * 60 + endM) - (startH * 60 + startM);
		return (durationMinutes / 60) * HOUR_HEIGHT;
	}

	function eventToTimeStrings(event: CalendarEvent): { start: string; end: string } {
		const startDate = new Date(event.start);
		const endDate = new Date(event.end);
		return {
			start: `${String(startDate.getHours()).padStart(2, '0')}:${String(startDate.getMinutes()).padStart(2, '0')}`,
			end: `${String(endDate.getHours()).padStart(2, '0')}:${String(endDate.getMinutes()).padStart(2, '0')}`
		};
	}

	async function commitPlan() {
		if (!schedule.length) return;

		committing = true;
		try {
			await api.llm.commitSchedule(
				schedule.map((slot) => ({
					task_id: slot.task_id,
					start_time: slot.start_time,
					end_time: slot.end_time
				}))
			);
			await tasks.load();
			close();
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to commit schedule';
		} finally {
			committing = false;
		}
	}

	function close() {
		$planModalOpen = false;
		plan = null;
		schedule = [];
		calendarEvents = [];
		error = null;
	}

	$effect(() => {
		if ($planModalOpen && !plan && !loading) {
			generatePlan();
		}
	});

	const hours = Array.from({ length: DAY_END_HOUR - DAY_START_HOUR }, (_, i) => DAY_START_HOUR + i);
</script>

{#if $planModalOpen}
	<div
		class="fixed inset-0 bg-black/50 flex items-start justify-center pt-[5vh] z-50 overflow-y-auto"
		onclick={close}
		role="dialog"
		tabindex="-1"
	>
		<div
			class="bg-white rounded-xl shadow-2xl w-full max-w-5xl mb-10"
			onclick={(e) => e.stopPropagation()}
			role="document"
		>
			<div class="p-4 border-b border-gray-100 flex items-center justify-between">
				<h2 class="text-lg font-semibold text-gray-900">Plan My Day</h2>
				<button onclick={close} class="text-gray-400 hover:text-gray-600">
					<svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
					</svg>
				</button>
			</div>

			{#if loading}
				<div class="p-12 text-center">
					<div class="inline-block w-8 h-8 border-2 border-gray-300 border-t-gray-900 rounded-full animate-spin"></div>
					<p class="mt-4 text-gray-600">Generating your plan...</p>
				</div>
			{:else if error}
				<div class="p-6">
					<div class="bg-red-50 text-red-700 p-4 rounded-lg">{error}</div>
					<button
						onclick={generatePlan}
						class="mt-4 px-4 py-2 text-sm bg-gray-900 text-white rounded-lg hover:bg-gray-800"
					>
						Try Again
					</button>
				</div>
			{:else if plan}
				<div class="flex">
					<!-- Left: Tasks -->
					<div class="flex-1 p-5 border-r border-gray-100 max-h-[70vh] overflow-y-auto">
						<p class="text-gray-700 text-sm mb-4">{plan.message}</p>

						<!-- Draggable task list -->
						<div class="mb-3 flex items-center justify-between">
							<h3 class="text-sm font-medium text-gray-700">Tasks</h3>
							<span class="text-xs text-gray-400">drag to reorder</span>
						</div>
						<div
							use:dndzone={{ items: schedule, flipDurationMs: 200, dropTargetStyle: {} }}
							onconsider={handleDndConsider}
							onfinalize={handleDndFinalize}
							class="space-y-2"
						>
							{#each schedule as slot (slot.id)}
								<div
									animate:flip={{ duration: 200 }}
									class="flex items-center gap-3 p-2.5 bg-gray-50 rounded-lg border border-gray-200 cursor-move hover:border-gray-300"
								>
									<div class="text-xs font-mono text-gray-500 w-20 flex-shrink-0">
										{slot.start_time}-{slot.end_time}
									</div>
									<div class="flex-1 min-w-0">
										<p class="text-sm font-medium text-gray-900 truncate">{slot.title}</p>
									</div>
									<div class="text-xs text-gray-400 flex-shrink-0">
										{slot.estimated_minutes}m
									</div>
								</div>
							{/each}
						</div>
					</div>

					<!-- Right: Calendar timeline -->
					<div class="w-80 p-4 max-h-[70vh] overflow-y-auto bg-gray-50">
						<h3 class="text-sm font-medium text-gray-700 mb-3">Today's Timeline</h3>
						<div class="relative" style="height: {(DAY_END_HOUR - DAY_START_HOUR) * HOUR_HEIGHT}px;">
							<!-- Hour lines -->
							{#each hours as hour}
								<div
									class="absolute left-0 right-0 border-t border-gray-200"
									style="top: {(hour - DAY_START_HOUR) * HOUR_HEIGHT}px;"
								>
									<span class="absolute -top-2.5 left-0 text-xs text-gray-400 bg-gray-50 pr-2">
										{hour}:00
									</span>
								</div>
							{/each}

							<!-- Calendar events (existing commitments) -->
							{#each calendarEvents.filter(e => !e.all_day) as event}
								{@const times = eventToTimeStrings(event)}
								<div
									class="absolute left-10 right-2 bg-gray-200 rounded px-2 py-1 text-xs overflow-hidden border border-gray-300"
									style="top: {timeToPosition(times.start)}px; height: {Math.max(durationToHeight(times.start, times.end), 20)}px;"
								>
									<span class="font-medium text-gray-700 truncate block">{event.title}</span>
								</div>
							{/each}

							<!-- Proposed task slots -->
							{#each schedule as slot, i}
								<div
									class="absolute left-10 right-2 bg-blue-100 rounded px-2 py-1 text-xs overflow-hidden border-2 border-blue-400"
									style="top: {timeToPosition(slot.start_time)}px; height: {Math.max(durationToHeight(slot.start_time, slot.end_time), 24)}px;"
								>
									<span class="font-medium text-blue-900 truncate block">{slot.title}</span>
									<span class="text-blue-600">{slot.start_time}</span>
								</div>
							{/each}
						</div>
					</div>
				</div>

				<div class="border-t border-gray-100 p-4 flex justify-between">
					<button
						onclick={generatePlan}
						disabled={loading}
						class="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg disabled:opacity-50"
					>
						Regenerate
					</button>
					<div class="flex gap-2">
						<button onclick={close} class="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg">
							Cancel
						</button>
						<button
							onclick={commitPlan}
							disabled={committing || schedule.length === 0}
							class="px-4 py-2 text-sm bg-gray-900 text-white rounded-lg hover:bg-gray-800 disabled:opacity-50"
						>
							{committing ? 'Saving...' : 'Commit'}
						</button>
					</div>
				</div>
			{/if}
		</div>
	</div>
{/if}
