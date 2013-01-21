#include "parse_request.h"
#include "ptreferential/ptreferential.h"

namespace navitia { namespace timetables {

routing::DateTime request_parser::parse_time(const std::string str_dt, const type::Data &data) {
    routing::DateTime result;
    std::string working_str = str_dt;

    if(working_str != "") {
        if(working_str.substr(0,1) == "T") {
            if(working_str.size() == 2)
                working_str = working_str.substr(0,1) + "0" + working_str.substr(1,2);
            if(working_str.size() == 3)
                working_str += "00";
            working_str = boost::lexical_cast<std::string>(data.meta.production_date.begin().year()) +
                    boost::lexical_cast<std::string>(data.meta.production_date.begin().month())+
                    boost::lexical_cast<std::string>(data.meta.production_date.begin().day()) + working_str;
        }
        auto ptime = boost::posix_time::from_iso_string(str_dt);
        result = routing::DateTime((ptime.date() - data.meta.production_date.begin()).days(), ptime.time_of_day().total_seconds());
    } else {
        struct parsetimeerror{};
        throw parsetimeerror();
    }

    return result;
}

request_parser::request_parser(const std::string &API, const std::string &request, const std::string &str_dt, const std::string &str_max_dt,
               const int nb_departures, const type::Data & data) {

    try {
        date_time = parse_time(str_dt, data);
    } catch(...) {
        pb_response.set_error(API+" / Probleme lors du parsage de datetime");
    }

    if((nb_departures == std::numeric_limits<int>::max()) && str_max_dt == "") {
        pb_response.set_error(API+" : Un des deux champs nb_departures ou max_datetime doit être renseigné");
    } else {
        if(str_max_dt != "") {
            try {
                max_datetime = parse_time(str_max_dt, data);
            } catch(...) {
                pb_response.set_error(API+" / Probleme lors du parsage de max_datetime");
            }
        }

        if(request!= "") {
            try {
                route_points = navitia::ptref::make_query(type::Type_e::eRoutePoint, request, data);
            } catch(ptref::ptref_parsing_error parse_error) {
                switch(parse_error.type){
                case ptref::ptref_parsing_error::error_type::partial_error: pb_response.set_error(API+" / PTReferential : On n'a pas réussi à parser toute la requête. Non-interprété : >>" + parse_error.more + "<<"); break;
                case ptref::ptref_parsing_error::error_type::global_error: pb_response.set_error(API+" / PTReferential : Impossible de parser la requête");
                case ptref::ptref_parsing_error::error_type::unknown_object: pb_response.set_error(API+"Objet NAViTiA inconnu : " + parse_error.more);
                }
            }
        }
    }
}

request_parser::request_parser(const std::string &API, const std::string &request, const std::string &str_dt, const std::string &change_time, const type::Data & data) {

    try {
        date_time = parse_time(str_dt, data);
        date_time = date_time - date_time.hour();
    } catch(...) {
        pb_response.set_error(API+" / Probleme lors du parsage de datetime");
    }

    try {
        max_datetime = parse_time(change_time, data);
        max_datetime = max_datetime - max_datetime.date() * routing::DateTime::NB_SECONDS_DAY;
        max_datetime = max_datetime + (date_time.date() + 1) * routing::DateTime::NB_SECONDS_DAY;
    }catch(...) {
        pb_response.set_error(API+" / Probleme lors du parsage de changetime");
    }

    if(request!= "") {
        try {
            route_points = navitia::ptref::make_query(type::Type_e::eRoutePoint, request, data);
        } catch(ptref::ptref_parsing_error parse_error) {
            switch(parse_error.type){
                case ptref::ptref_parsing_error::error_type::partial_error: pb_response.set_error(API+" / PTReferential : On n'a pas réussi à parser toute la requête. Non-interprété : >>" + parse_error.more + "<<"); break;
                case ptref::ptref_parsing_error::error_type::global_error: pb_response.set_error(API+" / PTReferential : Impossible de parser la requête");
                case ptref::ptref_parsing_error::error_type::unknown_object: pb_response.set_error(API+"Objet NAViTiA inconnu : " + parse_error.more);
            }
        }
    }
}

request_parser::request_parser(const std::string &API, const std::string str_dt, const type::Data & data) {
    try {
        date_time = parse_time(str_dt, data);
        date_time = date_time - date_time.hour();
    } catch(...) {
        pb_response.set_error(API+" / Probleme lors du parsage de datetime");
    }
}

}}