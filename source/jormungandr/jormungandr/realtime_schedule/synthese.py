# coding=utf-8

# Copyright (c) 2001-2016, Canal TP and/or its affiliates. All rights reserved.
#
# This file is part of Navitia,
#     the software to build cool stuff with public transport.
#
# Hope you'll enjoy and contribute to this project,
#     powered by Canal TP (www.canaltp.fr).
# Help us simplify mobility and open public transport:
#     a non ending quest to the responsive locomotion way of traveling!
#
# LICENCE: This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
# Stay tuned using
# twitter @navitia
# IRC #navitia on freenode
# https://groups.google.com/d/forum/navitia
# www.navitia.io
from __future__ import absolute_import, print_function, unicode_literals, division

from jormungandr.realtime_schedule.realtime_proxy import RealtimeProxy
from jormungandr.schedule import RealTimePassage
import xml.etree.ElementTree as et
from jormungandr.interfaces.parsers import date_time_format
import pytz
from flask import logging
import pybreaker
import requests as requests
from jormungandr import cache, app
from datetime import datetime, time
from jormungandr.utils import timestamp_to_datetime
from navitiacommon.ratelimit import RateLimiter
import redis

class FakeRateLimiter(object):
    def __init__(self, *args, **kwargs):
        pass

    def acquire(self, *args, **kwargs):
        return True

class SyntheseRoutePoint(object):

    def __init__(self, rt_id=None, sp_id=None):
        self.syn_route_id = rt_id
        self.syn_stop_point_id = sp_id

    def __key(self):
        return (self.syn_route_id, self.syn_stop_point_id)

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return self.__key() == other.__key()

    def __repr__(self):
        return "SyntheseRoutePoint({})".format(self.__key())


class Synthese(RealtimeProxy):
    """
    class managing calls to timeo external service providing real-time next passages
    """

    def __init__(self, id, service_url, timezone, object_id_tag=None, destination_id_tag=None, instance=None,
                 timeout=10, redis_host=None, redis_db=0,
                 redis_port=6379, redis_password=None, max_requests_by_second=15,
                 redis_namespace='jormungandr.rate_limiter', **kwargs):
        self.service_url = service_url
        self.timeout = timeout  # timeout in seconds
        self.rt_system_id = id
        self.object_id_tag = object_id_tag if object_id_tag else id
        self.destination_id_tag = destination_id_tag
        self.instance = instance
        self.breaker = pybreaker.CircuitBreaker(fail_max=app.config['CIRCUIT_BREAKER_MAX_SYNTHESE_FAIL'],
                                                reset_timeout=app.config['CIRCUIT_BREAKER_SYNTHESE_TIMEOUT_S'])
        self.timezone = pytz.timezone(timezone)
        if not redis_host:
            self.rate_limiter = FakeRateLimiter()
        else:
            self.rate_limiter = RateLimiter(conditions=[{'requests': max_requests_by_second, 'seconds': 1}],
                                            redis_host=redis_host, redis_port=redis_port, redis_db=redis_db,
                                            redis_password=redis_password, redis_namespace=redis_namespace)

    def __repr__(self):
        """
         used as the cache key. we use the rt_system_id to share the cache between servers in production
        """
        return self.rt_system_id

    @cache.memoize(app.config['CACHE_CONFIGURATION'].get('TIMEOUT_SYNTHESE', 30))
    def _call_synthese(self, url):
        """
        http call to synthese
        """
        try:
            if not self.rate_limiter.acquire(self.rt_system_id, block=False):
                return None#this should not be cached :(
            return self.breaker.call(requests.get, url, timeout=self.timeout)
        except pybreaker.CircuitBreakerError as e:
            logging.getLogger(__name__).error('Synthese RT service dead, using base '
                                              'schedule (error: {}'.format(e))
        except requests.Timeout as t:
            logging.getLogger(__name__).error('Synthese RT service timeout, using base '
                                              'schedule (error: {}'.format(t))
        except redis.ConnectionError:
            logging.getLogger(__name__).exception('there is an error with Redis')
        except:
            logging.getLogger(__name__).exception('Synthese RT error, using base schedule')
        return None

    def _get_next_passage_for_route_point(self, route_point, count=None, from_dt=None, current_dt=None):
        url = self._make_url(route_point, count, from_dt)
        if not url:
            return None
        logging.getLogger(__name__).debug('Synthese RT service , call url : {}'.format(url))
        r = self._call_synthese(url)
        if not r:
            return None

        if r.status_code != 200:
            # TODO better error handling, the response might be in 200 but in error
            logging.getLogger(__name__).error('Synthese RT service unavailable, impossible to query : {}'
                                              .format(r.url))
            return None

        logging.getLogger(__name__).debug("synthese response: {}".format(r.text))
        stop_point_id = str(route_point.fetch_stop_id(self.object_id_tag))
        route_id = str(route_point.fetch_route_id(self.object_id_tag))
        route_point = SyntheseRoutePoint(route_id, stop_point_id)
        m = self._get_synthese_passages(r.content)
        return m.get(route_point)# if there is nothing from synthese, we keep the base

    def _make_url(self, route_point, count=None, from_dt=None):
        """
        The url returns something like a departure on a stop point
        """

        stop_id = route_point.fetch_stop_id(self.object_id_tag)

        if not stop_id:
            # one a the id is missing, we'll not find any realtime
            logging.getLogger(__name__).debug('missing realtime id for {obj}: stop code={s}'.
                                              format(obj=route_point, s=stop_id))
            return None

        count_param = '&rn={c}'.format(c=count) if count else ''

        # if a custom datetime is provided we give it to timeo
        dt_param = '&date={dt}'.format(
            dt=self._timestamp_to_date(from_dt).strftime('%Y-%m-%d %H:%M')) if from_dt else ''

        url = "{base_url}?SERVICE=tdg&roid={stop_id}{count}{date}".format(base_url=self.service_url,
                                                                    stop_id=stop_id,
                                                                    count=count_param,
                                                                    date=dt_param)

        return url

    def _get_value(self, item, xpath, val):
        value = item.find(xpath)
        if value == None:
            logging.getLogger(__name__).debug("Path not found: {path}".format(path=xpath))
            return None
        return value.get(val)

    def _get_real_time_passage(self, xml_journey):
        '''
        :return RealTimePassage: object real time passage
        :param xml_journey: journey information
        exceptions :
            ValueError: Unable to parse datetime, day is out of range for month (for example)
        '''
        dt = date_time_format(xml_journey.get('dateTime'))
        utc_dt = self.timezone.normalize(self.timezone.localize(dt)).astimezone(pytz.utc)
        passage = RealTimePassage(utc_dt)
        passage.is_real_time = (xml_journey.get('realTime') == 'yes')
        return passage

    @staticmethod
    def _build(xml):
        try:
            root = et.fromstring(xml)
        except et.ParseError as e:
            logging.getLogger(__name__).error("invalid xml: {}".format(e.message))
            raise
        for xml_journey in root.findall('journey'):
            yield xml_journey

    def _get_synthese_passages(self, xml):
        result = {}
        for xml_journey in self._build(xml):
            route_point = SyntheseRoutePoint(xml_journey.get('routeId'), self._get_value(xml_journey, 'stop', 'id'))
            if route_point not in result:
                result[route_point] = []
            passage = self._get_real_time_passage(xml_journey)
            result[route_point].append(passage)
        return result

    def status(self):
        return {'id': self.rt_system_id,
                'timeout': self.timeout,
                'circuit_breaker': {'current_state': self.breaker.current_state,
                                    'fail_counter': self.breaker.fail_counter,
                                    'reset_timeout': self.breaker.reset_timeout},
                }

    def _timestamp_to_date(self, timestamp):
        dt = datetime.utcfromtimestamp(timestamp)
        dt = pytz.utc.localize(dt)
        return dt.astimezone(self.timezone)
