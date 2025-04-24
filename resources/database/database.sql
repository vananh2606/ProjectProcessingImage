BEGIN;

create table if not exists history(
    -- id INTEGER primary key autoincrement,
    step text not null,
    time_check text not null, 
    model_name text not null,
    result text not null,
    img_path text,
    code_sn text not null,
    weight text not null,
    error_type text);

COMMIT;