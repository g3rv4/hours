import os
from decimal import Decimal


def build_email(weeks, template, **tpl_args):
    # I _should_ use a real templating engine... but I want to get over this!
    weeks_lines = []
    period_total = 0
    for week in weeks:
        week_lines = []
        weekly_total = 0
        ordered_days = sorted(weeks[week].keys())
        week_lines.append('<tr><th colspan="4">&nbsp;<br/>Week %s<br/>&nbsp;</th></tr>' % week)
        week_lines.append('<tr><th>Day</th><th>Daily Total</th><th>Task</th><th>Task length</th></tr>')
        for day in ordered_days:
            tasks = weeks[week][day]
            daily_total = sum([int(t['length']) for t in tasks])
            weekly_total += daily_total
            week_lines.append(('<tr><td rowspan="{rowspan}">{day}</td><td rowspan="{rowspan}">{daily_total}</td>'
                                '<td>{task}</td><td>{task_duration}</td></tr>').
                               format(rowspan=len(tasks),
                                      day=day.strftime('%m/%d<br/>%A'),
                                      daily_total=secondsToTime(daily_total, True),
                                      task=tasks[0]['task_name'],
                                      task_duration=secondsToTime(tasks[0]['length'])))
            for task in tasks[1:]:
                week_lines.append('<tr><td>%s</td><td>%s</td></tr>' % (task['task_name'], secondsToTime(task['length'])))

        week_lines.append('<tr><td colspan="4" style="text-align:center;">&nbsp;<br/><b>Weekly total:</b> %s<br/>&nbsp;</td></tr>' %
                           secondsToTime(weekly_total, True))
        weeks_lines.append('\n'.join(week_lines))
        period_total += weekly_total

    weeks_html = '<table>%s</table>' % '<tr><td colspan="4">&nbsp;</td></tr>'.join(weeks_lines)
    if len(weeks) > 1:
        weeks_html += '<br/>&nbsp;<br/><b>Period total:</b> %s' % secondsToTime(period_total, True)

    with open(os.path.join(os.path.dirname(__file__), 'email/%s.html' % template)) as f:
        content = f.read()
        return content.format(weeks_html=weeks_html, **tpl_args)


def secondsToTime(seconds, include_decimal=False):
    seconds = int(seconds)
    mins, secs = divmod(seconds, 60)
    hours, mins = divmod(mins, 60)
    res = '%d:%02d:%02d' % (hours, mins, secs)
    if include_decimal:
        res += ' (%0.2f)' % (Decimal(seconds) / 3600)
    return res
