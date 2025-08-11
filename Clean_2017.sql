SELECT * FROM `PMIU_2017/18`.`public-census_oct_2018`;

CREATE TABLE `PMIU_2017/18`.`public-census_oct_2018_staging` LIKE `PMIU_2017/18`.`public-census_oct_2018`;
INSERT INTO `PMIU_2017/18`.`public-census_oct_2018_staging` SELECT * FROM `PMIU_2017/18`.`public-census_oct_2018`;
SELECT * FROM `PMIU_2017/18`.`public-census_oct_2018_staging`;


-- 0. Standardize 
 -- MOZA, PermA, Street Name, uc, headn, drinkwater, 
 
SELECT *
FROM `PMIU_2017/18`.`public-census_oct_2018_staging`

SELECT *
FROM `PMIU_2017/18`.`public-census_oct_2018_staging`
		 WHERE upgrade_primary_year IS NULL 
 	     OR upgrade_middle_year IS NULL 
		 OR upgrade_high_year IS NULL
;


-- SET SQL_SAFE_UPDATES = 0;
UPDATE `PMIU_2017/18`.`public-census_oct_2018_staging`
SET 
	upgrade_primary_year = 0, 
	upgrade_middle_year = 0, 
	upgrade_high_year = 0, 
	upgrade_high_sec_year = 0
WHERE 
	school_level = 'Primary';


SELECT * FROM `PMIU_2017/18`.`public-census_oct_2018_staging`;
SELECT * FROM `PMIU_2017/18`.`public-census_oct_2018_staging` WHERE moza = '';


SELECT
    SUBSTRING_INDEX(school_name, ' ', 1) AS classification,
    SUBSTRING(school_name, LOCATE(' ', school_name) + 1,
              LOCATE(' ', school_name, LOCATE(' ', school_name) + 1) - LOCATE(' ', school_name) - 1) AS middle_class,
    SUBSTRING_INDEX(school_name, ' ', -1) AS moza_missing
FROM Student;


SELECT
    -- First part (everything before the second space)
    SUBSTRING_INDEX(school_name, ' ', 1) AS classification,
    
    -- Last part (everything after the second space)
    LOWER(SUBSTRING(school_name, 
              LOCATE(' ', school_name, LOCATE(' ', school_name) + 1) + 1
             )) AS moza_missing
FROM `PMIU_2017/18`.`public-census_oct_2018_staging`;


UPDATE `PMIU_2017/18`.`public-census_oct_2018_staging`
SET 
    
    moza = LOWER(
        SUBSTRING(
            school_name, 
            LOCATE(' ', school_name, LOCATE(' ', school_name) + 1) + 1
        )
    )
WHERE 
    -- Optional: Apply conditions
    moza = '';  -- At least 2 spaces





-- 1. Remove Duplicates 	



