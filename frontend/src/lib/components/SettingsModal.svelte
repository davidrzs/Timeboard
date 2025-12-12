<script lang="ts">
	import { settings } from '../stores/settings';
	import { settingsModalOpen } from '../stores/ui';
	import type { SchedulingWindows, SchedulingWindow } from '../types';

	const DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'];
	const DAY_LABELS: Record<string, string> = {
		monday: 'Mon',
		tuesday: 'Tue',
		wednesday: 'Wed',
		thursday: 'Thu',
		friday: 'Fri',
		saturday: 'Sat',
		sunday: 'Sun'
	};
	const DEFAULT_WINDOWS: SchedulingWindow[] = [
		{ start: '09:00', end: '12:00' },
		{ start: '14:00', end: '18:00' }
	];

	let weekStartsOn = $state(1);
	let schedulingPreferences = $state('');
	let morningEmailEnabled = $state(true);
	let morningEmailTime = $state('06:00');
	let schedulingWindows = $state<SchedulingWindows>({});
	let saving = $state(false);

	$effect(() => {
		if ($settingsModalOpen) {
			weekStartsOn = $settings.week_starts_on;
			schedulingPreferences = $settings.scheduling_preferences;
			morningEmailEnabled = $settings.morning_email_enabled;
			morningEmailTime = $settings.morning_email_time;
			schedulingWindows = JSON.parse(JSON.stringify($settings.scheduling_windows || {}));
		}
	});

	function getWindowsForDay(day: string): SchedulingWindow[] {
		return schedulingWindows[day] || [];
	}

	function addWindow(day: string) {
		if (!schedulingWindows[day]) {
			schedulingWindows[day] = [];
		}
		// Add next logical window based on what's already there
		const existing = schedulingWindows[day];
		const nextWindow = existing.length === 0
			? { start: '09:00', end: '12:00' }
			: { start: '14:00', end: '18:00' };
		schedulingWindows[day] = [...existing, nextWindow];
	}

	function removeWindow(day: string, index: number) {
		schedulingWindows[day] = schedulingWindows[day].filter((_, i) => i !== index);
		if (schedulingWindows[day].length === 0) {
			delete schedulingWindows[day];
			schedulingWindows = { ...schedulingWindows };
		}
	}

	function updateWindow(day: string, index: number, field: 'start' | 'end', value: string) {
		schedulingWindows[day][index][field] = value;
		schedulingWindows = { ...schedulingWindows };
	}

	function close() {
		$settingsModalOpen = false;
	}

	async function handleSave() {
		saving = true;
		try {
			await settings.update({
				week_starts_on: weekStartsOn,
				scheduling_preferences: schedulingPreferences,
				morning_email_enabled: morningEmailEnabled,
				morning_email_time: morningEmailTime,
				scheduling_windows: schedulingWindows
			});
			close();
		} finally {
			saving = false;
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') close();
	}
</script>

{#if $settingsModalOpen}
	<div
		class="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
		onclick={close}
		onkeydown={handleKeydown}
		role="dialog"
		tabindex="-1"
	>
		<div
			class="bg-white rounded-xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto"
			onclick={(e) => e.stopPropagation()}
			onkeydown={(e) => e.stopPropagation()}
			role="document"
		>
			<div class="p-4 border-b border-gray-100">
				<h2 class="text-lg font-medium">Settings</h2>
			</div>

			<div class="p-4 space-y-5">
				<div>
					<label for="week-starts-on" class="block text-sm font-medium text-gray-700 mb-1">
						Week starts on
					</label>
					<select
						id="week-starts-on"
						bind:value={weekStartsOn}
						class="w-full text-sm border border-gray-200 rounded-lg px-3 py-2"
					>
						<option value={0}>Sunday</option>
						<option value={1}>Monday</option>
					</select>
				</div>

				<div class="border-t border-gray-100 pt-4">
					<label class="block text-sm font-medium text-gray-700 mb-2">
						Scheduling windows
					</label>
					<p class="text-xs text-gray-500 mb-3">Set available hours for task scheduling per day</p>

					<div class="space-y-3">
						{#each DAYS as day}
							{@const windows = getWindowsForDay(day)}
							<div class="flex items-center gap-3">
								<span class="text-sm font-medium text-gray-600 w-10 shrink-0">{DAY_LABELS[day]}</span>
								<div class="flex-1 flex flex-wrap items-center gap-2">
									{#if windows.length === 0}
										<span class="text-sm text-gray-400">9-12, 14-18</span>
										<button
											type="button"
											onclick={() => addWindow(day)}
											class="text-xs text-gray-400 hover:text-blue-600"
										>
											edit
										</button>
									{:else}
										{#each windows as window, i}
											<div class="flex items-center gap-1 bg-gray-50 rounded-lg px-2 py-1">
												<input
													type="time"
													value={window.start}
													onchange={(e) => updateWindow(day, i, 'start', e.currentTarget.value)}
													class="text-sm border-0 bg-transparent w-20 p-0"
												/>
												<span class="text-gray-400">-</span>
												<input
													type="time"
													value={window.end}
													onchange={(e) => updateWindow(day, i, 'end', e.currentTarget.value)}
													class="text-sm border-0 bg-transparent w-20 p-0"
												/>
												<button
													type="button"
													onclick={() => removeWindow(day, i)}
													class="text-gray-400 hover:text-red-500 ml-1"
												>
													&times;
												</button>
											</div>
										{/each}
										<button
											type="button"
											onclick={() => addWindow(day)}
											class="text-xs text-blue-600 hover:text-blue-800 px-2 py-1"
										>
											+
										</button>
									{/if}
								</div>
							</div>
						{/each}
					</div>
				</div>

				<div class="border-t border-gray-100 pt-4">
					<label for="scheduling-preferences" class="block text-sm font-medium text-gray-700 mb-1">
						Scheduling preferences
					</label>
					<textarea
						id="scheduling-preferences"
						bind:value={schedulingPreferences}
						placeholder="e.g., I prefer to do deep work in the morning..."
						rows="3"
						class="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 resize-none"
					></textarea>
					<p class="text-xs text-gray-500 mt-1">Used by "Plan My Day" to schedule your tasks</p>
				</div>

				<div class="border-t border-gray-100 pt-4">
					<div class="flex items-center justify-between">
						<div>
							<label for="morning-email" class="block text-sm font-medium text-gray-700">
								Morning email
							</label>
							<p class="text-xs text-gray-500">Daily summary of your tasks</p>
						</div>
						<button
							id="morning-email"
							type="button"
							onclick={() => (morningEmailEnabled = !morningEmailEnabled)}
							class="relative inline-flex h-6 w-11 items-center rounded-full transition-colors"
							class:bg-gray-900={morningEmailEnabled}
							class:bg-gray-200={!morningEmailEnabled}
							role="switch"
							aria-checked={morningEmailEnabled}
						>
							<span
								class="inline-block h-4 w-4 transform rounded-full bg-white transition-transform"
								class:translate-x-6={morningEmailEnabled}
								class:translate-x-1={!morningEmailEnabled}
							></span>
						</button>
					</div>

					{#if morningEmailEnabled}
						<div class="mt-3">
							<label for="email-time" class="block text-sm text-gray-500 mb-1">
								Send at
							</label>
							<input
								id="email-time"
								type="time"
								bind:value={morningEmailTime}
								class="text-sm border border-gray-200 rounded-lg px-3 py-2"
							/>
						</div>
					{/if}
				</div>
			</div>

			<div class="p-4 border-t border-gray-100 flex justify-end gap-2">
				<button
					onclick={close}
					class="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg"
				>
					Cancel
				</button>
				<button
					onclick={handleSave}
					disabled={saving}
					class="px-4 py-2 text-sm bg-gray-900 text-white rounded-lg hover:bg-gray-800 disabled:opacity-50"
				>
					{saving ? 'Saving...' : 'Save'}
				</button>
			</div>
		</div>
	</div>
{/if}
