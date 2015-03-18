import os
from decimal import Decimal


def build_email(weeks, template, **tpl_args):
    # I _should_ use a real templating engine... but I want to get over this!
    weeks_lines = []
    period_total = 0
    colors = ('#F0F0F0', '#FFFFFF')
    for week in weeks:
        iter = 0
        week_lines = []
        weekly_total = 0
        ordered_days = sorted(weeks[week].keys())
        week_lines.append('<tr><th colspan="5">&nbsp;<br/>Week %s<br/>&nbsp;</th></tr>' % week)
        week_lines.append('<tr><th>Day</th><th>Daily Total</th><th>Task length</th><th>Task</th><th>Comment</th></tr>')
        for day in ordered_days:
            bg = 'style="background-color:%s"' % colors[iter % len(colors)]
            tasks = weeks[week][day]
            daily_total = sum([int(t['length']) for t in tasks])
            weekly_total += daily_total
            week_lines.append(('<tr {bg}><td rowspan="{rowspan}">{day}</td><td rowspan="{rowspan}">{daily_total}</td>'
                                '<td>{task_duration}</td><td>{task}</td><td>{comment}&nbsp;</td></tr>').
                               format(rowspan=len(tasks),
                                      day=day.strftime('%m/%d<br/>%A'),
                                      daily_total=secondsToTime(daily_total, True),
                                      task=tasks[0]['issue'],
                                      task_duration=secondsToTime(tasks[0]['length']),
                                      bg=bg,
                                      comment=tasks[0]['comment']))
            for task in tasks[1:]:
                week_lines.append('<tr %s><td>%s</td><td>%s</td><td>%s</td></tr>' % (bg, secondsToTime(task['length']),
                                                                                     task['issue'], task['comment']))

            iter += 1

        week_lines.append('<tr><td colspan="5" style="text-align:center;">&nbsp;<br/><b>Weekly total:</b> %s<br/>&nbsp;</td></tr>' %
                           secondsToTime(weekly_total, True))
        weeks_lines.append('\n'.join(week_lines))
        period_total += weekly_total

    weeks_html = '<table style="border-collapse: collapse;" border="1">%s</table>' % '<tr><td colspan="5">&nbsp;</td></tr>'.join(weeks_lines)
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
