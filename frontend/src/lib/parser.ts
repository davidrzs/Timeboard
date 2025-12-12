import type { Project } from './types';

export interface QuickParsed {
	title: string;
	project: Project | null;
	duration: number | null;
	dueDate: Date | null;
	priority: number | null;
	rawMatches: {
		project?: string;
		duration?: string;
		date?: string;
		priority?: string;
	};
}

const DURATION_PATTERNS = [
	// Combined: 1h30m, 2h15m
	{ regex: /~?(\d+)h(\d+)m\b/i, parse: (m: RegExpMatchArray) => parseInt(m[1]) * 60 + parseInt(m[2]) },
	// Hours with decimal: 1.5h, 2.5hr, 0.5 hours
	{ regex: /~?(\d+(?:\.\d+)?)\s*(?:hrs?|hours?)\b/i, parse: (m: RegExpMatchArray) => Math.round(parseFloat(m[1]) * 60) },
	// Hours: 1h, 2hr
	{ regex: /~?(\d+)\s*h\b/i, parse: (m: RegExpMatchArray) => parseInt(m[1]) * 60 },
	// Minutes: 30m, 45min, 90 minutes
	{ regex: /~?(\d+)\s*(?:m|mins?|minutes?)\b/i, parse: (m: RegExpMatchArray) => parseInt(m[1]) },
];

const DATE_KEYWORDS: Record<string, () => Date> = {
	'today': () => new Date(),
	'tomorrow': () => {
		const d = new Date();
		d.setDate(d.getDate() + 1);
		return d;
	},
	'monday': () => nextWeekday(1),
	'tuesday': () => nextWeekday(2),
	'wednesday': () => nextWeekday(3),
	'thursday': () => nextWeekday(4),
	'friday': () => nextWeekday(5),
	'saturday': () => nextWeekday(6),
	'sunday': () => nextWeekday(0),
	'next week': () => {
		const d = new Date();
		d.setDate(d.getDate() + 7);
		return d;
	},
	'next monday': () => nextWeekday(1, true),
	'next tuesday': () => nextWeekday(2, true),
	'next wednesday': () => nextWeekday(3, true),
	'next thursday': () => nextWeekday(4, true),
	'next friday': () => nextWeekday(5, true),
	'next saturday': () => nextWeekday(6, true),
	'next sunday': () => nextWeekday(0, true),
};

function nextWeekday(day: number, forceNextWeek = false): Date {
	const d = new Date();
	const currentDay = d.getDay();
	let diff = day - currentDay;
	if (diff <= 0 || forceNextWeek) diff += 7;
	d.setDate(d.getDate() + diff);
	return d;
}

export function parseQuick(text: string, projects: Project[]): QuickParsed {
	let title = text;
	let project: Project | null = null;
	let duration: number | null = null;
	let dueDate: Date | null = null;
	let priority: number | null = null;
	const rawMatches: QuickParsed['rawMatches'] = {};

	// Extract priority (!1, !2, !3)
	const priorityMatch = text.match(/!([1-3])\b/);
	if (priorityMatch) {
		priority = parseInt(priorityMatch[1]);
		rawMatches.priority = priorityMatch[0];
		title = title.replace(priorityMatch[0], '').trim();
	}

	// Extract #project
	const hashtagMatch = text.match(/#(\S+)/);
	if (hashtagMatch) {
		const tag = hashtagMatch[1].toLowerCase();
		const matched = projects.find(p =>
			p.name.toLowerCase() === tag ||
			p.name.toLowerCase().startsWith(tag) ||
			p.name.toLowerCase().includes(tag)
		);
		if (matched) {
			project = matched;
			rawMatches.project = hashtagMatch[0];
			title = title.replace(hashtagMatch[0], '').trim();
		}
	}

	// Extract duration (~30m, ~1h, ~1h30m)
	for (const pattern of DURATION_PATTERNS) {
		const match = text.match(pattern.regex);
		if (match) {
			duration = pattern.parse(match);
			rawMatches.duration = match[0];
			title = title.replace(match[0], '').trim();
			break;
		}
	}

	// Extract date keywords (by friday, due tomorrow, etc.)
	const datePatterns = [
		/\b(?:by|due|on|before)\s+(today|tomorrow|(?:next\s+)?(?:mon|tues|wednes|thurs|fri|satur|sun)day|next\s+week)\b/i,
		/\b(today|tomorrow)\b/i,
	];

	for (const pattern of datePatterns) {
		const match = text.match(pattern);
		if (match) {
			const keyword = match[1].toLowerCase();
			const dateGetter = DATE_KEYWORDS[keyword];
			if (dateGetter) {
				dueDate = dateGetter();
				rawMatches.date = match[0];
				title = title.replace(match[0], '').trim();
				break;
			}
		}
	}

	// Clean up extra spaces
	title = title.replace(/\s+/g, ' ').trim();

	return { title, project, duration, dueDate, priority, rawMatches };
}

export function formatDuration(minutes: number): string {
	if (minutes < 60) return `${minutes}m`;
	const h = Math.floor(minutes / 60);
	const m = minutes % 60;
	return m > 0 ? `${h}h ${m}m` : `${h}h`;
}

export function formatDate(date: Date): string {
	const today = new Date();
	today.setHours(0, 0, 0, 0);
	const target = new Date(date);
	target.setHours(0, 0, 0, 0);

	const diffDays = Math.round((target.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));

	if (diffDays === 0) return 'Today';
	if (diffDays === 1) return 'Tomorrow';
	if (diffDays > 1 && diffDays < 7) {
		return target.toLocaleDateString('en-US', { weekday: 'long' });
	}
	return target.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}
