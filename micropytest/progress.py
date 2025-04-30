from rich.progress import Progress, TextColumn, BarColumn, SpinnerColumn, TimeElapsedColumn, TimeRemainingColumn


class TestProgress:
    def __init__(self, show_progress, total_tests):
        if show_progress:
            self.progress = Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(complete_style="green", finished_style="green", pulse_style="yellow", bar_width=None),
                TextColumn("{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                TimeRemainingColumn(),
                TextColumn("{task.fields[stats]}"),
                expand=False,
            )
            self.task_id = self.progress.add_task(
                "[cyan]Running tests...",
                total=total_tests,
                stats="[green]  0✓[/green] [red]  0✗[/red] [magenta]  0→[/magenta] [yellow]  0⚠[/yellow] "
            )
        else:
            self.progress = None
            self.task_id = None

    def update(self, counts):
        if self.progress:
            description = '[green]Running tests...'
            stats = (
                f"[green]{counts.passed:3d}✓[/green] [red]{counts.failed:3d}✗[/red] "
                f"[magenta]{counts.skipped:3d}→[/magenta] [yellow]{counts.warnings:3d}⚠[/yellow] "
            )
            self.progress.update(self.task_id, advance=1, description=description, stats=stats)

    def __enter__(self):
        if self.progress:
            self.progress.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.progress:
            self.progress.stop()
