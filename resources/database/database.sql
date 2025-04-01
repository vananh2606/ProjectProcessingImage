BEGIN;

create table if not exists history(
    -- id INTEGER primary key autoincrement,
    camera text not null,
    model text not null,
    result text not null,
    time_check text not null, 
    img_path text,
    code text,
    error_type text);

COMMIT;