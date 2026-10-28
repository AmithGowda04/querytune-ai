SELECT DepartmentID, Name FROM dbo.Department WHERE DepartmentID NOT IN (SELECT DepartmentID FROM dbo.Employee WHERE HireDate < '2020-01-01');
