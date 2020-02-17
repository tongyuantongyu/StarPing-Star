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

routeCode = {
    0: "!N",
    1: "!H",
    2: "!P",
    4: "!F",
    5: "!S",
    13: "!X",
    14: "!V",
    15: "!C",
};

function getRoute(eid, target_name, node_name, time_after) {
    if (isNaN(time_after)) {
        let toastHTML = '<span>Hmm...This is not a valid time.</span>';
        M.toast({html: toastHTML});
        return false
    }
    $.getJSON("/api/route",
        {
            "target": target_name,
            "node": node_name,
            "time": time_after
        },
        function (timedata) {
        if (timedata.time == null) {
            $(eid).empty();
            let toastHTML = '<span>Oops. There is no record after this time.</span>';
            M.toast({html: toastHTML});
        }
            let time = timedata.time * 1000;
            let data = timedata.data;
            let s = '<div class="card-panel teal lighten-4">Route data at time ' + new Date(time) + '</div>' +
                '<div style="overflow: auto"><table class="striped" style="min-width:500px">' +
                '<thead><tr><th style="width:2%">#</th><th>IP</th>' +
                '<th style="width:5%">Avg/ms</th><th style="width:5%">Min/ms</th><th style="width:5%">Max/ms</th>' +
                '<th style="width:5%">SDev/ms</th><th style="width:5%">D/T</th></tr></thead><tbody>';
            if (data.length === 0) {
                s += '</tbody></table></div>';
                $(eid).empty();
                $(eid).append(s);
                let toastHTML = '<span>Oops. MTR of that time was timed out.</span>';
                M.toast({html: toastHTML});
            } else {
                for (let hop of data) {
                    let l = '<tr><td style="width:2%">';
                    l += hop['index'] + '</td>';
                    if (hop['timeout']) {
                        l += '<td>*</td><td></td><td></td><td></td><td></td><td></td></tr>';
                        s += l;
                    } else {
                        l += renderAddr(hop['addr'][0]);
                        l += '<td style="width:5%">' + hop['avg'].toFixed(2) + '</td>';
                        l += '<td style="width:5%">' + hop['min'].toFixed(2) + '</td>';
                        l += '<td style="width:5%">' + hop['max'].toFixed(2) + '</td>';
                        l += '<td style="width:5%">' + hop['std_dev'].toFixed(2) + '</td>';
                        l += '<td style="width:5%">' + hop['drop'] + '/' + hop['total'] + '</td></tr>';
                        s += l;
                        if (hop['addr'].length > 1) {
                            for (let ex_addr of hop['addr'].slice(1))
                                s += '<tr><td style="width:2%"> </td>' + renderAddr(ex_addr) + '</tr>';
                        }
                    }
                }
                s += '</tbody></table></div>';
                $(eid).empty();
                $(eid).append(s);
                $('.with-rdns').tooltip();
            }
        });
    return true
}

function renderAddr(addr) {
    let l = '';
    if (addr['rdns'] !== "") {
        l += '<td class="tooltipped with-rdns" data-position="left" data-tooltip="' + addr['rdns'] + '">'
    } else {
        l += '<td>'
    }
    l += addr['ip'];
    if (addr['code'] < 256) {
        l += ' ';
        if (routeCode[addr['code']] !== undefined) {
            l += routeCode[addr['code']]
        } else {
            l += '!<' + routeCode[addr['code']] + '>'
        }
    }
    l += '</td>';
    return l;
}

