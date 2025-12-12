import { driver } from 'driver.js';
import 'driver.js/dist/driver.css';
import { api } from './api';

export function startTour(onComplete?: () => void) {
	const driverObj = driver({
		showProgress: true,
		animate: true,
		overlayColor: 'rgba(0, 0, 0, 0.5)',
		stagePadding: 8,
		popoverClass: 'planner-tour',
		steps: [
			{
				popover: {
					title: 'Welcome to Planner',
					description:
						'A quick tour to help you get started. You can organize tasks by time horizon or project, schedule them on a calendar, and add tasks quickly with natural language.',
					side: 'over',
					align: 'center'
				}
			},
			{
				element: '[data-tour="quick-add"]',
				popover: {
					title: 'Quick Add',
					description:
						'Press Cmd+K (or click here) to quickly add tasks. Use natural language like "review draft by friday #work ~1h" to set project, due date, and time estimate.',
					side: 'bottom',
					align: 'center'
				}
			},
			{
				element: '[data-tour="view-toggle"]',
				popover: {
					title: 'Board & Calendar Views',
					description:
						'Switch between Board view (kanban-style columns) and Calendar view (weekly schedule) to manage your tasks.',
					side: 'bottom',
					align: 'start'
				}
			},
			{
				element: '[data-tour="group-toggle"]',
				popover: {
					title: 'Group by Lists or Timeline',
					description:
						'In Board view, group tasks by project (Lists) or by time horizon (Timeline). Drag tasks between columns to reorganize.',
					side: 'bottom',
					align: 'start'
				}
			},
			{
				popover: {
					title: 'You\'re all set!',
					description:
						'Drag tasks to reorder or move between columns. Double-click to edit. In Calendar view, drag unscheduled tasks onto the calendar to schedule them.',
					side: 'over',
					align: 'center'
				}
			}
		],
		onDestroyed: async () => {
			try {
				await api.settings.update({ has_seen_tour: true });
			} catch (e) {
				console.error('Failed to save tour completion', e);
			}
			onComplete?.();
		}
	});

	driverObj.drive();
}
