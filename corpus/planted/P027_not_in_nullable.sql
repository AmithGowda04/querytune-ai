SELECT EmployeeID, FullName FROM dbo.Employee WHERE EmployeeID NOT IN (SELECT ManagerID FROM dbo.Employee);
