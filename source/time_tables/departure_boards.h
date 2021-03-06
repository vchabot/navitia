/* Copyright © 2001-2014, Canal TP and/or its affiliates. All rights reserved.
  
This file is part of Navitia,
    the software to build cool stuff with public transport.
 
Hope you'll enjoy and contribute to this project,
    powered by Canal TP (www.canaltp.fr).
Help us simplify mobility and open public transport:
    a non ending quest to the responsive locomotion way of traveling!
  
LICENCE: This program is free software; you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
   
This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU Affero General Public License for more details.
   
You should have received a copy of the GNU Affero General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.
  
Stay tuned using
twitter @navitia 
IRC #navitia on freenode
https://groups.google.com/d/forum/navitia
www.navitia.io
*/

#pragma once
#include "type/pb_converter.h"
#include "routing/routing.h"
#include "routing/get_stop_times.h"


namespace navitia { namespace timetables {
typedef std::vector<DateTime> vector_datetime;
typedef std::pair<routing::SpIdx, routing::RouteIdx> stop_point_route;
typedef std::vector<routing::datetime_stop_time> vector_dt_st;

void departure_board(PbCreator& pb_creator, const std::string &filter,
                     boost::optional<const std::string> calendar_id,
                     const std::vector<std::string>& forbidden_uris,
                     const boost::posix_time::ptime datetime,
                     uint32_t duration, uint32_t depth,
                     int count, int start_page,
                     const type::RTLevel rt_level,
                     const size_t items_per_route_point);


bool between_opening_and_closing(const time_duration& me,
                                 const time_duration& opening,
                                 const time_duration& closing);

time_duration length_of_time(const time_duration& duration_1,
                             const time_duration& duration_2);

bool line_closed (const time_duration& duration,
                  const time_duration& opening,
                  const time_duration& closing,
                  const pt::ptime& date );

}}
