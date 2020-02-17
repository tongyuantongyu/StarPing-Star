// StarPing Star
// Copyright (C) 2020  Yuan Tong
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program.  If not, see <https://www.gnu.org/licenses/>.

function setChartGlance(eid, oldChart = null, oldInterval = null, target_name, target_sname, span) {
    span = parseInt(span);
    if (oldChart != null) {
        oldChart.clear();
        oldChart.dispose()
    }
    if (oldInterval != null) {
        clearInterval(oldInterval)
    }
    const myChart = echarts.init(document.getElementById(eid));
    myChart.showLoading();

    const max_point = 60 * span;
    const gap = 60;

    let option = {
        animation: true,
        title: {
            text: 'StarPing Server Latency',
            subtext: target_sname,
            left: 'center'
        },
        legend: {
            show: true,
            bottom: '0'
        },
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'cross',
                animation: true,
                label: {
                    backgroundColor: '#ccc',
                    borderColor: '#aaa',
                    borderWidth: 1,
                    shadowBlur: 0,
                    shadowOffsetX: 0,
                    shadowOffsetY: 0,
                    textStyle: {
                        color: '#222'
                    },
                }
            },
            formatter: function (params) {
                const date = new Date(parseFloat(params[0].axisValue) * 1000);
                const dword = [
                    date.getFullYear().toString().padStart(4, '0'),
                    (date.getMonth() + 1).toString().padStart(2, '0'),
                    date.getDate().toString().padStart(2, '0')
                ].join('-');
                const time = [
                    date.getHours().toString().padStart(2, '0'),
                    date.getMinutes().toString().padStart(2, '0'),
                    date.getSeconds().toString().padStart(2, '0'),
                ].join(':');
                let tooltip = '<table><tr><td colspan="3">' + dword + ' ' + time + '</td></tr>';
                for (let p of params) {
                    tooltip += '<tr><td>' + p.marker + '</td>';
                    tooltip += '<td>' + p.seriesName + '</td>';
                    if (p.value[1] == null) {
                        tooltip += '<td>Timeout.</td></tr>'
                    } else {
                        tooltip += '<td>' + p.value[1].toFixed(2) + 'ms</td></tr>'
                    }
                }
                return tooltip + '</table>'
            }
        },
        grid: {
            left: '0%',
            right: '0%',
            bottom: $(window).width() < 601 ? '15%' : '10%',
            containLabel: true
        },
        xAxis: {
            z: 100,
            type: 'time',
            axisLabel: {
                formatter: function (value) {
                    const date = new Date(parseFloat(value) * 1000);
                    const time = [
                        date.getHours().toString().padStart(2, '0'),
                        date.getMinutes().toString().padStart(2, '0'),
                        date.getSeconds().toString().padStart(2, '0'),
                    ].join(':');
                    if (span > 6) {
                        const dword = [
                            date.getFullYear().toString().padStart(4, '0'),
                            (date.getMonth() + 1).toString().padStart(2, '0'),
                            date.getDate().toString().padStart(2, '0')
                        ].join('-');
                        return dword + ' ' + time
                    }
                    return time
                }
            },
            axisPointer: {
                label: {
                    formatter: function (params) {
                        const date = new Date(parseFloat(params.value) * 1000);
                        return [
                            date.getHours().toString().padStart(2, '0'),
                            date.getMinutes().toString().padStart(2, '0'),
                            date.getSeconds().toString().padStart(2, '0'),
                        ].join(':')
                    }
                },
                z: 110
            },
            splitLine: {
                show: false
            },
            axisLine: {onZero: false},
            boundaryGap: false
        },
        yAxis: {
            z: 100,
            axisLabel: {
                inside: true,
                showMinLabel: false,
                margin: 2,
                formatter: function (val) {
                    return val.toFixed(0) + 'ms';
                },
                backgroundColor: 'rgba(255,255,255,0.75)',
                borderWidth: 6,
                borderRadius: 3
            },
            axisTrick: {
                inside: true
            },
            axisPointer: {
                inside: true,
                label: {
                    formatter: function (params) {
                        return params.value.toFixed(2) + 'ms';
                    }
                },
                z: 110
            },
            max: function (value) {
                return value.max * 1.1;
            },
            min: 0,
            boundaryGap: [0, 0],
            splitNumber: 3,
            splitLine: {
                show: false
            },
            splitArea: {
                show: true
            }
        },
        series: [],
    };

    let newest = {};
    let nodeindex = {};
    let newstamp;
    let index = 0;
    let now = (new Date()).getTime() / 1000;

    let failed = true;

    $.ajax(span === 1 ? "/api/record" : "/api/record/longterm",
        {
            data: span === 1 ? {
                "target": target_name
            } : {
                "target": target_name,
                "span": span
            },
            dataType: "json",
            success: function (data) {
                let series = [];
                for (let node of data) {
                    let set_data = [];
                    nodeindex[node.name] = index;
                    index++;
                    if (node.data != null) {
                        for (let record of node.data) {
                            if (record["timeout"]) {
                                set_data.push([record["stamp"], null])
                            } else {
                                set_data.push([record["stamp"], record["avg"]])
                            }
                        }
                    }
                    series.push({
                        id: nodeindex[node.name],
                        type: 'line',
                        name: node.shown_name,
                        smooth: true,
                        animation: true,
                        data: set_data,
                        showSymbol: $(window).width() > 1024 && span === 1,
                    });
                    if (node.data != null) {
                        newest[node.name] = set_data[set_data.length - 1][0];
                    } else {
                        newest[node.name] = now;
                    }
                }
                newstamp = Math.min.apply(null, Object.values(newest)) + 1;
                option.series = series;
                myChart.setOption(option);
                console.log("Loaded. Newest: " + newstamp);
                failed = false;
                myChart.hideLoading();
            },
            statusCode: {
                429: function () {
                    let toastHTML = '<span>Whoa, you operates too fast. Please wait a moment.</span>';
                    M.toast({html: toastHTML});
                    myChart.clear();
                    myChart.dispose();
                }
            }
        });

    if (failed) {
        return [null, null]
    }

    return [setInterval(function () {
        let now = (new Date()).getTime() / 1000;

        $.getJSON("/api/record",
            {
                "target": target_name,
                "update": true,
                "stamp": newstamp
            },
            function (data) {
                let series = [];
                for (let node of data) {
                    let set_data = [];

                    if (nodeindex[node.name] !== undefined) {
                        set_data = option.series[nodeindex[node.name]].data;
                    }
                    if (node.data != null) {
                        for (let record of node.data) {
                            if (newest[node.name] >= record["stamp"]) continue;
                            if (record["timeout"]) {
                                set_data.push([record["stamp"], null])
                            } else {
                                set_data.push([record["stamp"], record["avg"]])
                            }
                            if (set_data.length > max_point) {
                                set_data = set_data.slice(set_data.length - max_point)
                            }
                        }
                    }
                    series.push({
                        id: nodeindex[node.name],
                        type: 'line',
                        name: node.shown_name,
                        smooth: true,
                        animation: true,
                        data: set_data,
                        showSymbol: $(window).width() > 1024,
                    });
                    if (node.data != null) {
                        newest[node.name] = set_data[set_data.length - 1][0];
                    } else {
                        newest[node.name] = now;
                    }
                }
                let newOption = {series: series};
                myChart.setOption(newOption);
                newstamp = Math.min.apply(null, Object.values(newest)) + 1;
                console.log("Updated. Newest: " + newstamp);
            });
    }, 60 * 1000 + 1), myChart]
}

function setChartDetail(eid, oldChart = null, oldInterval = null, target_name, target_sname, node_name, node_sname, span) {
    span = parseInt(span);
    if (oldChart != null) {
        oldChart.clear();
        oldChart.dispose()
    }
    if (oldInterval != null) {
        clearInterval(oldInterval)
    }
    const myChart = echarts.init(document.getElementById(eid));
    myChart.showLoading();

    const max_point = 1440 * span;
    const gap = 60;

    let avg = [], min = [], max = [];

    let option = {
        animation: false,
        title: {
            text: 'StarPing Server Latency',
            subtext: target_sname + ' from ' + node_sname,
            left: 'center',
            top: $(window).width() < 601 ? '7%' : '0',
        },
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'cross',
                label: {
                    backgroundColor: '#ccc',
                    borderColor: '#aaa',
                    borderWidth: 1,
                    shadowBlur: 0,
                    shadowOffsetX: 0,
                    shadowOffsetY: 0,
                    textStyle: {
                        color: '#222'
                    }
                }
            },
            formatter: function (params) {
                const date = new Date(parseFloat(params[0].axisValue) * 1000);
                const dword = [
                    date.getFullYear().toString().padStart(4, '0'),
                    (date.getMonth() + 1).toString().padStart(2, '0'),
                    date.getDate().toString().padStart(2, '0')
                ].join('-');
                const time = [
                    date.getHours().toString().padStart(2, '0'),
                    date.getMinutes().toString().padStart(2, '0'),
                    date.getSeconds().toString().padStart(2, '0'),
                ].join(':');
                if (!params[0].value[2]) {
                    if (params[0].value[1] == null) {
                        return dword + ' ' + time + '<br />' +
                            'Node down.<br />';
                    }
                    return dword + ' ' + time + '<br />' +
                        'Average: ' + params[0].value[1].toFixed(2) + 'ms<br />' +
                        'Lowest: ' + params[1].value[1].toFixed(2) + 'ms<br />' +
                        'Highest: ' + (params[1].value[1] + params[2].value[1]).toFixed(2) + 'ms<br />' +
                        'SDeviation: ' + (params[2].value[2]).toFixed(2) + 'ms<br />' +
                        'Dropped: ' + params[2].value[3] + '/' + params[2].value[4] + '<br />';
                } else {
                    return dword + ' ' + time + '<br />' +
                        'Timeout.<br />' +
                        'Dropped: ' + params[2].value[3] + '/' + params[2].value[4] + '<br />';
                }
            }
        },
        grid: {
            top: $(window).width() < 601 ? '18%' : '12%',
            left: '0%',
            right: '0%',
            bottom: '10%',
            containLabel: true
        },
        xAxis: {
            z: 100,
            type: 'time',
            axisLabel: {
                formatter: function (value) {
                    const date = new Date(parseFloat(value) * 1000);
                    const time = [
                        date.getHours().toString().padStart(2, '0'),
                        date.getMinutes().toString().padStart(2, '0'),
                        date.getSeconds().toString().padStart(2, '0'),
                    ].join(':');
                    const dword = [
                        date.getFullYear().toString().padStart(4, '0'),
                        (date.getMonth() + 1).toString().padStart(2, '0'),
                        date.getDate().toString().padStart(2, '0')
                    ].join('-');
                    return dword + ' ' + time
                }
            },
            axisPointer: {
                label: {
                    formatter: function (params) {
                        const date = new Date(parseFloat(params.value) * 1000);
                        return [
                            date.getHours().toString().padStart(2, '0'),
                            date.getMinutes().toString().padStart(2, '0'),
                            date.getSeconds().toString().padStart(2, '0'),
                        ].join(':')
                    }
                },
                z: 110
            },
            splitLine: {
                show: false
            },
            axisLine: {onZero: false},
            boundaryGap: false
        },
        yAxis: {
            z: 100,
            axisLabel: {
                inside: true,
                showMinLabel: false,
                margin: 2,
                formatter: function (val) {
                    return val.toFixed(0) + 'ms';
                },
                backgroundColor: 'rgba(255,255,255,0.75)',
                borderWidth: 6,
                borderRadius: 3
            },
            axisTrick: {
                inside: true
            },
            axisPointer: {
                label: {
                    formatter: function (params) {
                        return params.value.toFixed(2) + 'ms';
                    }
                },
                z: 110
            },
            max: function (value) {
                return value.max * 1.25;
            },
            min: 0,
            boundaryGap: [0.2, 0.2],
            splitNumber: 5,
            splitLine: {
                show: false
            },
            splitArea: {
                show: true
            }
        },
        dataZoom: [{
            type: 'inside',
            start: 100 - (30 / span),
            end: 100,
            minSpan: 5 / span
        }, {
            start: 100 - (30 / span),
            end: 100,
            minSpan: 5 / span,
            handleIcon: 'M10.7,11.9v-1.3H9.3v1.3c-4.9,0.3-8.8,4.4-8.8,9.4c0,5,3.9,9.1,8.8,9.4v1.3h1.3v-1.3c4.9-0.3,8.8-4.4,8.8-9.4C19.5,16.3,15.6,12.2,10.7,11.9z M13.3,24.4H6.7V23h6.6V24.4z M13.3,19.6H6.7v-1.4h6.6V19.6z',
            handleSize: '80%',
            handleStyle: {
                color: '#fff',
                shadowBlur: 3,
                shadowColor: 'rgba(0, 0, 0, 0.6)',
                shadowOffsetX: 2,
                shadowOffsetY: 2
            },
            labelFormatter: function (_, timeString) {
                const date = new Date(parseFloat(timeString) * 1000);
                return [
                    date.getHours().toString().padStart(2, '0'),
                    date.getMinutes().toString().padStart(2, '0'),
                    date.getSeconds().toString().padStart(2, '0'),
                ].join(':');
            }
        }],
        series: [
            {
                type: 'line',
                smooth: true,
                data: avg,
                animation: false,
                itemStyle: {
                    normal: {
                        color: '#636465'
                    }
                },
                showSymbol: false
            }, {
                name: 'L',
                type: 'bar',
                data: min,
                barWidth: '100%',
                itemStyle: {
                    normal: {
                        barBorderColor: 'rgba(0,0,0,0)',
                        color: 'rgba(0,0,0,0)'
                    },
                    emphasis: {
                        barBorderColor: 'rgba(0,0,0,0)',
                        color: 'rgba(0,0,0,0)'
                    }
                },
                stack: 'range',
                symbol: 'none'
            }, {
                name: 'U',
                type: 'bar',
                data: max,
                barWidth: '100%',
                stack: 'range',
                symbol: 'none',
                markArea: {
                    silent: true,
                    data: [],
                    itemStyle: {
                        color: 'rgba(235,40,49,0.50)',
                    }
                },
            }],
        brush: {
            xAxisIndex: 'all',
            brushLink: 'all',
            toolbox: ['rect', 'lineX', 'keep', 'clear'],
            outOfBrush: {
                opacity: 0.2
            }
        },
        toolbox: {
            feature: {
                dataZoom: {
                    yAxisIndex: 'none'
                },
                restore: {},
                saveAsImage: {}
            }
        },
        visualMap: [
            {
                show: false,
                type: 'continuous',
                seriesIndex: 2,
                dimension: 3,
                min: 0,
                max: 10,
                inRange: {
                    color: ['#1bd747', '#dee10c', '#e1a127', '#d94046']
                }
            }
        ]
    };

    let newest;
    let out = false;
    let out_start;
    let out_range = [];
    let failed = true;

    $.ajax(span === 1 ? "/api/detailRecord" : "/api/detailRecord/longterm",
        {
            data: span === 1 ? {
                "node": node_name,
                "target": target_name
            } : {
                "node": node_name,
                "target": target_name,
                "span": span
            },
            dataType: "json",
            success: function (data) {
                let t = 0;
                if (data.time == null) {
                    let toastHTML = '<span>Oops. Seems there\'s no data now.</span><button class="btn-flat toast-action" onClick="goBack()">Back</button>';
                    M.toast({html: toastHTML});
                    myChart.clear();
                    myChart.dispose();
                    return
                }
                for (let i = 0; i < data.time.length; i++) {
                    if (data.avg[i] !== 0) {
                        if (out) {
                            out_range.push([{xAxis: out_start}, {xAxis: data.time[i]}]);
                            out = false;
                        }
                        if (t !== 0 && data.time[i] - t > 1.1 * gap) {
                            avg.push([avg[avg.length - 1][0] + gap, null, avg[avg.length - 1][2]]);
                            min.push([min[min.length - 1][0] + gap, null]);
                            max.push([max[max.length - 1][0] + gap, null, null, null, null]);
                            avg.push([data.time[i] - gap, null, data.timeout[i]]);
                            min.push([data.time[i] - gap, null]);
                            max.push([data.time[i] - gap, null, null, null, null])
                        }
                        avg.push([data.time[i], data.avg[i], data.timeout[i]]);
                        min.push([data.time[i], data.min[i]]);
                        max.push([data.time[i], data.max[i] - data.min[i], data.std_dev[i], data.drop[i], data.total[i]])
                    } else {
                        if (!out) {
                            out_start = data.time[i - 1];
                            out = true;
                        }
                        avg.push([data.time[i], null, data.timeout[i]]);
                        min.push([data.time[i], null]);
                        max.push([data.time[i], null, null, data.drop[i], data.total[i]])
                    }
                    t = data.time[i]
                }
                if (out) {
                    out_range.push([{xAxis: out_start}, {xAxis: avg[avg.length - 1][0]}]);
                }
                option.series[2].markArea.data = out_range;
                newest = avg[avg.length - 1][0];
                myChart.setOption(option);
                console.log("Loaded. Newest: " + newest);
                failed = false;
                myChart.hideLoading();
            },
            statusCode: {
                429: function () {
                    let toastHTML = '<span>Whoa, you operates too fast. Please wait a moment.</span>';
                    M.toast({html: toastHTML});
                    myChart.clear();
                    myChart.dispose();
                }
            }
        });

    if (failed) {
        return [null, null]
    }

    return [setInterval(function () {
        $.getJSON("/api/detailRecord",
            {
                "node": node_name,
                "target": target_name,
                "update": true,
                "stamp": newest
            },
            function (data) {
                if (data.time == null) {
                    console.log("Newest. Newest: " + newest);
                    return
                }
                if (out) {
                    out_range = option.series[2].markArea.data.slice(0, -1);
                } else {
                    out_range = option.series[2].markArea.data;
                }
                let avg = option.series[0].data;
                let min = option.series[1].data;
                let max = option.series[2].data;
                let start = avg.length + data.time.length - max_point;
                if (start < 0) start = 0;
                let t = 0;
                for (let i = 0; i < data.time.length; i++) {
                    if (data.avg[i] !== 0) {
                        if (out) {
                            out_range.push([{xAxis: out_start}, {xAxis: data.time[i]}]);
                            out = false;
                        }
                        if (t !== 0 && data.time[i] - t > gap) {
                            avg.push([avg[avg.length - 1][0] + gap, null, avg[avg.length - 1][2]]);
                            min.push([min[min.length - 1][0] + gap, null]);
                            max.push([max[max.length - 1][0] + gap, null, null, null, null]);
                            avg.push([data.time[i] - gap, null, data.timeout[i]]);
                            min.push([data.time[i] - gap, null]);
                            max.push([data.time[i] - gap, null, null, null, null])
                        }
                        avg.push([data.time[i], data.avg[i], data.timeout[i]]);
                        min.push([data.time[i], data.min[i]]);
                        max.push([data.time[i], data.max[i] - data.min[i], data.std_dev[i], data.drop[i], data.total[i]])
                    } else {
                        if (!out) {
                            out_start = data.time[i];
                            out = true;
                        }
                        avg.push([data.time[i], null, data.timeout[i]]);
                        min.push([data.time[i], null]);
                        max.push([data.time[i], null, null, data.drop[i], data.total[i]])
                    }
                    t = data.time[i]
                }
                if (out) {
                    out_range.push([{xAxis: out_start}, {xAxis: avg[avg.length - 1][0]}]);
                }
                avg = avg.slice(start);
                min = min.slice(start);
                max = max.slice(start);
                let newOption = {
                    series: [
                        {
                            data: avg,
                        }, {
                            data: min,
                        }, {
                            data: max,
                            markArea: {
                                data: out_range
                            }
                        }]
                };
                myChart.setOption(newOption);
                newest = avg[avg.length - 1][0];
                console.log("Updated. Newest: " + newest);
            });
    }, 60 * 1000 + 1), myChart];
}