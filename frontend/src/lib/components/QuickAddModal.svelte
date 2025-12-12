<script lang="ts">
	import { quickAddOpen } from '../stores/ui';
	import { tasks } from '../stores/tasks';
	import { activeProjects } from '../stores/projects';
	import { parseQuick, type QuickParsed } from '../parser';

	let input = $state('');
	let quickParsed = $state<QuickParsed | null>(null);

	let editedTitle = $state('');
	let editedProjectId = $state<number | null>(null);
	let editedDueDate = $state<string | null>(null);
	let editedEstimate = $state<number | null>(null);
	let editedPriority = $state<number | null>(null);

	// Project autocomplete for List field
	let projectSearch = $state('');
	let showProjectDropdown = $state(false);
	let highlightedIndex = $state(0);

	let filteredProjects = $derived(
		projectSearch.trim()
			? $activeProjects.filter((p) =>
					p.name.toLowerCase().includes(projectSearch.toLowerCase())
				)
			: $activeProjects
	);

	let selectedProjectName = $derived(
		editedProjectId ? $activeProjects.find((p) => p.id === editedProjectId)?.name ?? '' : ''
	);

	function selectProject(id: number | null, name: string) {
		editedProjectId = id;
		projectSearch = name;
		showProjectDropdown = false;
	}

	function handleProjectKeydown(e: KeyboardEvent) {
		if (!showProjectDropdown) {
			if (e.key === 'ArrowDown' || e.key === 'Enter') {
				showProjectDropdown = true;
				e.preventDefault();
			}
			return;
		}

		if (e.key === 'ArrowDown') {
			highlightedIndex = Math.min(highlightedIndex + 1, filteredProjects.length);
			e.preventDefault();
		} else if (e.key === 'ArrowUp') {
			highlightedIndex = Math.max(highlightedIndex - 1, 0);
			e.preventDefault();
		} else if (e.key === 'Enter') {
			if (highlightedIndex === 0) {
				selectProject(null, '');
			} else {
				const project = filteredProjects[highlightedIndex - 1];
				if (project) selectProject(project.id, project.name);
			}
			e.preventDefault();
		} else if (e.key === 'Escape') {
			showProjectDropdown = false;
			e.preventDefault();
		}
	}

	// Inline autocomplete for main input
	let showInlineAutocomplete = $state<'project' | 'date' | null>(null);
	let inlineHighlightedIndex = $state(0);
	let hashtagQuery = $state('');
	let dateQuery = $state('');

	const DATE_OPTIONS = [
		'today',
		'tomorrow',
		'monday',
		'tuesday',
		'wednesday',
		'thursday',
		'friday',
		'saturday',
		'sunday',
		'next week',
		'next monday',
		'next tuesday',
		'next wednesday',
		'next thursday',
		'next friday'
	];

	let inlineFilteredProjects = $derived(
		hashtagQuery
			? $activeProjects.filter((p) =>
					p.name.toLowerCase().includes(hashtagQuery.toLowerCase())
				)
			: $activeProjects
	);

	let inlineFilteredDates = $derived(
		dateQuery
			? DATE_OPTIONS.filter((d) => d.toLowerCase().startsWith(dateQuery.toLowerCase()))
			: DATE_OPTIONS.slice(0, 5)
	);

	function getHashtagMatch(text: string): { query: string; start: number; end: number } | null {
		const match = text.match(/#(\S*)$/);
		if (match) {
			return {
				query: match[1],
				start: match.index!,
				end: match.index! + match[0].length
			};
		}
		return null;
	}

	function getDateMatch(text: string): { query: string; start: number; end: number; prefix: string } | null {
		// Match "by/due/on <word>" or standalone date keywords at end
		const prefixMatch = text.match(/\b(by|due|on)\s+(\S*)$/i);
		if (prefixMatch) {
			return {
				query: prefixMatch[2],
				start: prefixMatch.index!,
				end: prefixMatch.index! + prefixMatch[0].length,
				prefix: prefixMatch[1]
			};
		}
		return null;
	}

	function handleInputChange() {
		// Check for project hashtag first
		const hashMatch = getHashtagMatch(input);
		if (hashMatch) {
			hashtagQuery = hashMatch.query;
			dateQuery = '';
			showInlineAutocomplete = 'project';
			inlineHighlightedIndex = 0;
			return;
		}

		// Check for date keywords
		const dateMatch = getDateMatch(input);
		if (dateMatch) {
			dateQuery = dateMatch.query;
			hashtagQuery = '';
			showInlineAutocomplete = 'date';
			inlineHighlightedIndex = 0;
			return;
		}

		showInlineAutocomplete = null;
		hashtagQuery = '';
		dateQuery = '';
	}

	function selectInlineProject(projectName: string) {
		const match = getHashtagMatch(input);
		if (match) {
			input = input.slice(0, match.start) + '#' + projectName + ' ' + input.slice(match.end);
		}
		showInlineAutocomplete = null;
		hashtagQuery = '';
	}

	function selectInlineDate(dateOption: string) {
		const match = getDateMatch(input);
		if (match) {
			input = input.slice(0, match.start) + match.prefix + ' ' + dateOption + ' ' + input.slice(match.end);
		}
		showInlineAutocomplete = null;
		dateQuery = '';
	}

	function getCurrentAutocompleteItems(): string[] {
		if (showInlineAutocomplete === 'project') {
			return inlineFilteredProjects.map(p => p.name);
		} else if (showInlineAutocomplete === 'date') {
			return inlineFilteredDates;
		}
		return [];
	}

	function handleMainInputKeydown(e: KeyboardEvent) {
		const items = getCurrentAutocompleteItems();
		if (showInlineAutocomplete && items.length > 0) {
			if (e.key === 'ArrowDown') {
				inlineHighlightedIndex = Math.min(inlineHighlightedIndex + 1, items.length - 1);
				e.preventDefault();
				return;
			} else if (e.key === 'ArrowUp') {
				inlineHighlightedIndex = Math.max(inlineHighlightedIndex - 1, 0);
				e.preventDefault();
				return;
			} else if (e.key === 'Tab' || e.key === 'Enter') {
				if (showInlineAutocomplete === 'project') {
					const project = inlineFilteredProjects[inlineHighlightedIndex];
					if (project) {
						selectInlineProject(project.name);
						e.preventDefault();
						return;
					}
				} else if (showInlineAutocomplete === 'date') {
					const dateOption = inlineFilteredDates[inlineHighlightedIndex];
					if (dateOption) {
						selectInlineDate(dateOption);
						e.preventDefault();
						return;
					}
				}
			} else if (e.key === 'Escape') {
				showInlineAutocomplete = null;
				e.preventDefault();
				return;
			}
		}

		// Default behavior
		if (e.key === 'Escape') {
			close();
		} else if (e.key === 'Enter' && !e.shiftKey && input.trim() && !showInlineAutocomplete) {
			e.preventDefault();
			handleSubmit();
		}
	}

	// Instant parsing and form fill as user types
	$effect(() => {
		if (input.trim()) {
			const parsed = parseQuick(input, $activeProjects);
			quickParsed = parsed;

			// Auto-fill form fields
			editedTitle = parsed.title;
			editedProjectId = parsed.project?.id ?? null;
			projectSearch = parsed.project?.name ?? '';
			editedEstimate = parsed.duration;
			editedPriority = parsed.priority;
			if (parsed.dueDate) {
				editedDueDate = parsed.dueDate.toISOString().split('T')[0];
			} else {
				editedDueDate = null;
			}
		} else {
			quickParsed = null;
			editedTitle = '';
			editedProjectId = null;
			projectSearch = '';
			editedDueDate = null;
			editedEstimate = null;
			editedPriority = null;
		}
	});

	// Generate highlighted HTML for the input text
	function getHighlightedText(): string {
		if (!quickParsed || !input) return '';

		let text = escapeHtml(input);
		const replacements: { original: string; html: string }[] = [];

		if (quickParsed.rawMatches.project) {
			replacements.push({
				original: escapeHtml(quickParsed.rawMatches.project),
				html: `<mark class="bg-blue-200 text-blue-800 rounded-sm">${escapeHtml(quickParsed.rawMatches.project)}</mark>`
			});
		}
		if (quickParsed.rawMatches.duration) {
			replacements.push({
				original: escapeHtml(quickParsed.rawMatches.duration),
				html: `<mark class="bg-green-200 text-green-800 rounded-sm">${escapeHtml(quickParsed.rawMatches.duration)}</mark>`
			});
		}
		if (quickParsed.rawMatches.date) {
			replacements.push({
				original: escapeHtml(quickParsed.rawMatches.date),
				html: `<mark class="bg-amber-200 text-amber-800 rounded-sm">${escapeHtml(quickParsed.rawMatches.date)}</mark>`
			});
		}
		if (quickParsed.rawMatches.priority) {
			replacements.push({
				original: escapeHtml(quickParsed.rawMatches.priority),
				html: `<mark class="bg-red-200 text-red-800 rounded-sm">${escapeHtml(quickParsed.rawMatches.priority)}</mark>`
			});
		}

		// Sort by length descending to replace longer matches first
		replacements.sort((a, b) => b.original.length - a.original.length);

		for (const { original, html } of replacements) {
			text = text.replace(original, html);
		}

		return text;
	}

	function escapeHtml(str: string): string {
		return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
	}

	function reset() {
		input = '';
		quickParsed = null;
		editedTitle = '';
		editedProjectId = null;
		projectSearch = '';
		showProjectDropdown = false;
		editedDueDate = null;
		editedEstimate = null;
		editedPriority = null;
		showInlineAutocomplete = null;
		hashtagQuery = '';
		dateQuery = '';
	}

	function close() {
		$quickAddOpen = false;
		reset();
	}

	async function handleSubmit() {
		if (!editedTitle.trim()) return;

		await tasks.create({
			title: editedTitle,
			project_id: editedProjectId,
			due_date: editedDueDate,
			estimated_minutes: editedEstimate,
			priority: editedPriority
		});

		close();
	}

	</script>

{#if $quickAddOpen}
	<div
		class="fixed inset-0 bg-black/50 flex items-start justify-center pt-[20vh] z-50"
		onclick={close}
		role="dialog"
		tabindex="-1"
	>
		<div
			class="bg-white rounded-xl shadow-2xl w-full max-w-xl"
			onclick={(e) => e.stopPropagation()}
			role="document"
		>
			<div class="p-4">
				<div class="relative">
					<input
						type="text"
						bind:value={input}
						oninput={handleInputChange}
						onkeydown={handleMainInputKeydown}
						placeholder="review draft by friday #work ~1h"
						class="w-full text-lg border-0 outline-none placeholder-gray-400 bg-transparent relative z-10 caret-black"
						style="color: transparent;"
						autofocus
					/>
					<!-- Highlighted text overlay -->
					<div
						class="absolute inset-0 text-lg pointer-events-none whitespace-pre"
						aria-hidden="true"
					>
						{#if input}
							{@html getHighlightedText()}
						{/if}
					</div>

					<!-- Inline project autocomplete -->
					{#if showInlineAutocomplete === 'project' && inlineFilteredProjects.length > 0}
						<div class="absolute top-full left-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-50 max-h-48 overflow-y-auto min-w-[200px]">
							{#each inlineFilteredProjects as project, i}
								<button
									type="button"
									class="w-full text-left px-3 py-2 text-sm hover:bg-gray-100 flex items-center gap-2 {inlineHighlightedIndex === i ? 'bg-gray-100' : ''}"
									onmousedown={() => selectInlineProject(project.name)}
								>
									<span
										class="w-2 h-2 rounded-full flex-shrink-0"
										style="background-color: {project.color}"
									></span>
									{project.name}
								</button>
							{/each}
						</div>
					{/if}

					<!-- Inline date autocomplete -->
					{#if showInlineAutocomplete === 'date' && inlineFilteredDates.length > 0}
						<div class="absolute top-full left-0 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-50 max-h-48 overflow-y-auto min-w-[200px]">
							{#each inlineFilteredDates as dateOption, i}
								<button
									type="button"
									class="w-full text-left px-3 py-2 text-sm hover:bg-gray-100 flex items-center gap-2 {inlineHighlightedIndex === i ? 'bg-gray-100' : ''}"
									onmousedown={() => selectInlineDate(dateOption)}
								>
									<svg class="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
									</svg>
									{dateOption}
								</button>
							{/each}
						</div>
					{/if}
				</div>
			</div>

			{#if input.trim()}
				<div class="border-t border-gray-100 p-4 space-y-3">
					<div class="flex items-center gap-3">
						<label class="text-sm text-gray-500 w-20">Title</label>
						<input
							type="text"
							bind:value={editedTitle}
							class="flex-1 text-sm border border-gray-200 rounded px-2 py-1"
						/>
					</div>

					<div class="flex items-center gap-3">
						<label class="text-sm text-gray-500 w-20">List</label>
						<div class="flex-1 relative">
							<input
								type="text"
								bind:value={projectSearch}
								onfocus={() => { showProjectDropdown = true; highlightedIndex = 0; }}
								onblur={() => setTimeout(() => showProjectDropdown = false, 150)}
								onkeydown={handleProjectKeydown}
								oninput={() => { highlightedIndex = 0; editedProjectId = null; }}
								placeholder="None"
								class="w-full text-sm border border-gray-200 rounded px-2 py-1"
							/>
							{#if showProjectDropdown}
								<div class="absolute top-full left-0 right-0 mt-1 bg-white border border-gray-200 rounded shadow-lg z-50 max-h-48 overflow-y-auto">
									<button
										type="button"
										class="w-full text-left px-2 py-1.5 text-sm hover:bg-gray-100 {highlightedIndex === 0 ? 'bg-gray-100' : ''}"
										onmousedown={() => selectProject(null, '')}
									>
										None
									</button>
									{#each filteredProjects as project, i}
										<button
											type="button"
											class="w-full text-left px-2 py-1.5 text-sm hover:bg-gray-100 flex items-center gap-2 {highlightedIndex === i + 1 ? 'bg-gray-100' : ''}"
											onmousedown={() => selectProject(project.id, project.name)}
										>
											<span
												class="w-2 h-2 rounded-full flex-shrink-0"
												style="background-color: {project.color}"
											></span>
											{project.name}
										</button>
									{/each}
									{#if filteredProjects.length === 0 && projectSearch.trim()}
										<div class="px-2 py-1.5 text-sm text-gray-400">No matches</div>
									{/if}
								</div>
							{/if}
						</div>
					</div>

					<div class="flex items-center gap-3">
						<label class="text-sm text-gray-500 w-20">Due</label>
						<input
							type="date"
							bind:value={editedDueDate}
							class="flex-1 text-sm border border-gray-200 rounded px-2 py-1"
						/>
					</div>

					<div class="flex items-center gap-3">
						<label class="text-sm text-gray-500 w-20">Estimate</label>
						<input
							type="number"
							bind:value={editedEstimate}
							placeholder="minutes"
							class="flex-1 text-sm border border-gray-200 rounded px-2 py-1"
						/>
					</div>

					<div class="flex items-center gap-3">
						<label class="text-sm text-gray-500 w-20">Priority</label>
						<select
							bind:value={editedPriority}
							class="flex-1 text-sm border border-gray-200 rounded px-2 py-1"
						>
							<option value={null}>None</option>
							<option value={1}>High</option>
							<option value={2}>Medium</option>
							<option value={3}>Low</option>
						</select>
					</div>
				</div>

				<div class="border-t border-gray-100 p-4 flex justify-end gap-2">
					<button
						onclick={close}
						class="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg"
					>
						Cancel
					</button>
					<button
						onclick={handleSubmit}
						class="px-4 py-2 text-sm bg-gray-900 text-white rounded-lg hover:bg-gray-800"
					>
						Create Task
					</button>
				</div>
			{/if}
		</div>
	</div>
{/if}
